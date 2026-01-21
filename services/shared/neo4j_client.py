"""
Neo4j Client for OSINT v2.0
Handles entity graph creation, relationships, and graph algorithms
"""

from neo4j import GraphDatabase
from typing import List, Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)


class Neo4jClient:
    """Neo4j client for entity correlation and graph analysis"""
    
    def __init__(self, uri: str, auth: tuple):
        """
        Initialize Neo4j client
        
        Args:
            uri: Neo4j connection URI (bolt://host:7687)
            auth: Tuple of (username, password)
        """
        self.driver = GraphDatabase.driver(uri, auth=auth)
        self.logger = logging.getLogger(__name__)
    
    def close(self):
        """Close driver connection"""
        self.driver.close()
    
    # ============================================================
    # INITIALIZATION
    # ============================================================
    
    def initialize_constraints(self):
        """Create all necessary constraints and indices"""
        constraints = [
            "CREATE CONSTRAINT entity_unique IF NOT EXISTS FOR (e:Entity) REQUIRE (e.name, e.type) IS NODE KEY",
            "CREATE CONSTRAINT finding_unique IF NOT EXISTS FOR (f:Finding) REQUIRE f.finding_id IS UNIQUE",
            "CREATE CONSTRAINT job_unique IF NOT EXISTS FOR (j:Job) REQUIRE j.job_id IS UNIQUE",
        ]
        
        indices = [
            "CREATE INDEX entity_type_idx IF NOT EXISTS FOR (e:Entity) ON (e.type)",
            "CREATE INDEX entity_source_idx IF NOT EXISTS FOR (e:Entity) ON (e.source)",
            "CREATE INDEX finding_job_idx IF NOT EXISTS FOR (f:Finding) ON (f.job_id)",
            "CREATE INDEX finding_confidence_idx IF NOT EXISTS FOR (f:Finding) ON (f.confidence)",
        ]
        
        with self.driver.session() as session:
            for constraint in constraints:
                try:
                    session.run(constraint)
                    self.logger.info(f"Created constraint")
                except Exception as e:
                    self.logger.warning(f"Constraint exists or error: {e}")
            
            for index in indices:
                try:
                    session.run(index)
                    self.logger.info(f"Created index")
                except Exception as e:
                    self.logger.warning(f"Index exists or error: {e}")
    
    # ============================================================
    # ENTITY OPERATIONS
    # ============================================================
    
    def create_entity(
        self,
        name: str,
        entity_type: str,
        properties: Optional[Dict] = None
    ) -> str:
        """
        Create or update entity node
        
        Args:
            name: Entity name (unique identifier)
            entity_type: Type of entity (person, organization, email, etc.)
            properties: Additional properties
        
        Returns:
            Entity ID
        """
        properties = properties or {}
        properties['name'] = name
        properties['type'] = entity_type
        
        with self.driver.session() as session:
            result = session.run("""
                MERGE (e:Entity {name: $name, type: $type})
                ON CREATE SET e.created_at = datetime(), e += $properties
                ON MATCH SET e.last_seen = datetime(), e += $properties
                RETURN e.name as entity_id
            """, name=name, type=entity_type, properties=properties)
            
            record = result.single()
            return record['entity_id'] if record else None
    
    def get_entity(self, name: str, entity_type: str) -> Optional[Dict]:
        """Get entity by name and type"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (e:Entity {name: $name, type: $type})
                RETURN e
            """, name=name, type=entity_type)
            
            record = result.single()
            if record:
                return dict(record['e'])
            return None
    
    def get_entities_by_type(self, entity_type: str, limit: int = 100) -> List[Dict]:
        """Get all entities of a specific type"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (e:Entity {type: $type})
                RETURN e
                LIMIT $limit
            """, type=entity_type, limit=limit)
            
            return [dict(record['e']) for record in result]
    
    # ============================================================
    # FINDING OPERATIONS
    # ============================================================
    
    def create_finding_node(self, finding_id: str, finding_data: Dict) -> bool:
        """Create finding node"""
        with self.driver.session() as session:
            session.run("""
                MERGE (f:Finding {finding_id: $finding_id})
                ON CREATE SET f += $properties, f.created_at = datetime()
                ON MATCH SET f += $properties
            """, finding_id=finding_id, properties=finding_data)
            return True
    
    def link_finding_to_job(self, finding_id: str, job_id: str) -> bool:
        """Create relationship between finding and job"""
        with self.driver.session() as session:
            session.run("""
                MATCH (f:Finding {finding_id: $finding_id})
                MERGE (j:Job {job_id: $job_id})
                MERGE (j)-[r:HAS_FINDING]->(f)
                ON CREATE SET r.created_at = datetime()
            """, finding_id=finding_id, job_id=job_id)
            return True
    
    # ============================================================
    # RELATIONSHIP OPERATIONS
    # ============================================================
    
    def link_entity_to_finding(
        self,
        entity_name: str,
        entity_type: str,
        finding_id: str,
        rel_type: str = "FOUND_IN",
        properties: Optional[Dict] = None
    ) -> bool:
        """
        Create relationship between entity and finding
        
        Args:
            entity_name: Entity identifier
            entity_type: Entity type
            finding_id: Finding UUID
            rel_type: Relationship type
            properties: Additional relationship properties
        
        Returns:
            Success boolean
        """
        properties = properties or {}
        
        with self.driver.session() as session:
            session.run(f"""
                MATCH (e:Entity {{name: $entity_name, type: $entity_type}})
                MATCH (f:Finding {{finding_id: $finding_id}})
                MERGE (e)-[r:{rel_type}]->(f)
                ON CREATE SET r.created_at = datetime(), r += $properties
                ON MATCH SET r.last_seen = datetime(), r += $properties
            """, entity_name=entity_name, entity_type=entity_type, 
                 finding_id=finding_id, properties=properties)
            return True
    
    def link_entities(
        self,
        entity1_name: str,
        entity1_type: str,
        entity2_name: str,
        entity2_type: str,
        rel_type: str,
        properties: Optional[Dict] = None
    ) -> bool:
        """Create relationship between two entities"""
        properties = properties or {}
        
        with self.driver.session() as session:
            session.run(f"""
                MATCH (e1:Entity {{name: $name1, type: $type1}})
                MATCH (e2:Entity {{name: $name2, type: $type2}})
                MERGE (e1)-[r:{rel_type}]->(e2)
                ON CREATE SET r.created_at = datetime(), r += $properties
                ON MATCH SET r.weight = COALESCE(r.weight, 0) + 1, r += $properties
            """, name1=entity1_name, type1=entity1_type,
                 name2=entity2_name, type2=entity2_type, properties=properties)
            return True
    
    # ============================================================
    # GRAPH QUERIES
    # ============================================================
    
    def get_entity_connections(
        self,
        entity_name: str,
        entity_type: str,
        max_depth: int = 2,
        limit: int = 50
    ) -> List[Dict]:
        """
        Get all connections for an entity up to max_depth
        
        Args:
            entity_name: Entity identifier
            entity_type: Entity type
            max_depth: Maximum relationship depth
            limit: Maximum results
        
        Returns:
            List of connected entities with relationship info
        """
        with self.driver.session() as session:
            result = session.run("""
                MATCH path = (e1:Entity {name: $name, type: $type})-[*1..""" + str(max_depth) + """]->(e2:Entity)
                RETURN e2 as entity, length(path) as distance, relationships(path) as rels
                ORDER BY distance
                LIMIT $limit
            """, name=entity_name, type=entity_type, limit=limit)
            
            connections = []
            for record in result:
                connections.append({
                    'entity': dict(record['entity']),
                    'distance': record['distance'],
                    'relationships': [dict(rel) for rel in record['rels']]
                })
            return connections
    
    def get_shortest_path(
        self,
        entity1_name: str,
        entity1_type: str,
        entity2_name: str,
        entity2_type: str
    ) -> Optional[Dict]:
        """Find shortest path between two entities"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (e1:Entity {name: $name1, type: $type1})
                MATCH (e2:Entity {name: $name2, type: $type2})
                MATCH path = shortestPath((e1)-[*..10]-(e2))
                RETURN nodes(path) as nodes, relationships(path) as rels, length(path) as distance
            """, name1=entity1_name, type1=entity1_type,
                 name2=entity2_name, type2=entity2_type)
            
            record = result.single()
            if record:
                return {
                    'nodes': [dict(node) for node in record['nodes']],
                    'relationships': [dict(rel) for rel in record['rels']],
                    'distance': record['distance']
                }
            return None
    
    def find_communities(
        self,
        job_id: str,
        min_cluster_size: int = 3
    ) -> List[Dict]:
        """
        Find communities/clusters of related entities
        Uses Louvain community detection algorithm
        
        Note: Requires GDS library in Neo4j
        """
        with self.driver.session() as session:
            # Create projection
            session.run("""
                CALL gds.graph.project.cypher(
                    'entity-graph-""" + job_id + """',
                    'MATCH (e:Entity) RETURN id(e) AS id',
                    'MATCH (e1:Entity)-[r]-(e2:Entity) RETURN id(e1) AS source, id(e2) AS target'
                )
            """)
            
            # Run community detection
            result = session.run("""
                CALL gds.louvain.stream('entity-graph-""" + job_id + """')
                YIELD nodeId, communityId
                MATCH (e:Entity) WHERE id(e) = nodeId
                RETURN communityId, collect(e.name) as members, count(*) as size
                WHERE size >= $min_size
                ORDER BY size DESC
            """, min_size=min_cluster_size)
            
            communities = []
            for record in result:
                communities.append({
                    'community_id': record['communityId'],
                    'members': record['members'],
                    'size': record['size']
                })
            
            # Drop projection
            session.run("CALL gds.graph.drop('entity-graph-" + job_id + "')")
            
            return communities
    
    def get_central_entities(self, job_id: str, limit: int = 10) -> List[Dict]:
        """
        Get most central/important entities using PageRank
        
        Returns entities sorted by importance
        """
        with self.driver.session() as session:
            result = session.run("""
                MATCH (j:Job {job_id: $job_id})-[:HAS_FINDING]->(f:Finding)<-[:FOUND_IN]-(e:Entity)
                WITH e, count(DISTINCT f) as finding_count
                MATCH (e)-[r]-()
                WITH e, finding_count, count(r) as relationship_count
                RETURN e.name as name, e.type as type, 
                       finding_count, relationship_count,
                       finding_count + relationship_count as centrality_score
                ORDER BY centrality_score DESC
                LIMIT $limit
            """, job_id=job_id, limit=limit)
            
            return [dict(record) for record in result]
    
    # ============================================================
    # JOB OPERATIONS
    # ============================================================
    
    def get_job_graph(self, job_id: str) -> Dict:
        """Get complete graph for a job"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (j:Job {job_id: $job_id})-[:HAS_FINDING]->(f:Finding)
                OPTIONAL MATCH (e:Entity)-[:FOUND_IN]->(f)
                RETURN j, collect(DISTINCT f) as findings, collect(DISTINCT e) as entities
            """, job_id=job_id)
            
            record = result.single()
            if record:
                return {
                    'job': dict(record['j']),
                    'findings': [dict(f) for f in record['findings']],
                    'entities': [dict(e) for e in record['entities'] if e]
                }
            return {}
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def get_statistics(self, job_id: Optional[str] = None) -> Dict:
        """Get graph statistics"""
        with self.driver.session() as session:
            if job_id:
                result = session.run("""
                    MATCH (j:Job {job_id: $job_id})-[:HAS_FINDING]->(f:Finding)
                    OPTIONAL MATCH (e:Entity)-[:FOUND_IN]->(f)
                    RETURN 
                        count(DISTINCT f) as findings_count,
                        count(DISTINCT e) as entities_count,
                        count(DISTINCT e.type) as entity_types_count
                """, job_id=job_id)
            else:
                result = session.run("""
                    MATCH (f:Finding)
                    OPTIONAL MATCH (e:Entity)-[:FOUND_IN]->(f)
                    RETURN 
                        count(DISTINCT f) as findings_count,
                        count(DISTINCT e) as entities_count,
                        count(DISTINCT e.type) as entity_types_count
                """)
            
            record = result.single()
            return dict(record) if record else {}
    
    # ============================================================
    # CLEANUP OPERATIONS
    # ============================================================
    
    def delete_job_graph(self, job_id: str) -> int:
        """Delete all nodes and relationships for a job"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (j:Job {job_id: $job_id})-[:HAS_FINDING]->(f:Finding)
                OPTIONAL MATCH (e:Entity)-[r:FOUND_IN]->(f)
                DETACH DELETE j, f, r
                RETURN count(f) as deleted_count
            """, job_id=job_id)
            
            record = result.single()
            return record['deleted_count'] if record else 0
    
    def cleanup_orphaned_entities(self) -> int:
        """Remove entities with no relationships"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (e:Entity)
                WHERE NOT (e)-[]-()
                DELETE e
                RETURN count(e) as deleted_count
            """)
            
            record = result.single()
            return record['deleted_count'] if record else 0
    
    # ============================================================
    # UTILITY METHODS
    # ============================================================
    
    def health_check(self) -> bool:
        """Check Neo4j connection health"""
        try:
            with self.driver.session() as session:
                result = session.run("RETURN 1 as test")
                return result.single()['test'] == 1
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False
