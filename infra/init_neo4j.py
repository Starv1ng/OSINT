"""
Initialize Neo4j constraints and indices for OSINT v2.0
Run this script to set up the graph database
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services'))

from shared.neo4j_client import Neo4jClient
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Initialize Neo4j constraints and indices"""
    # Connect to Neo4j
    neo4j_client = Neo4jClient(
        uri="bolt://localhost:7687",
        auth=("neo4j", "password123")
    )
    
    logger.info("Creating Neo4j constraints and indices...")
    
    try:
        neo4j_client.initialize_constraints()
        logger.info("✓ Successfully created constraints and indices")
        
        # Health check
        if neo4j_client.health_check():
            logger.info("✓ Neo4j health check passed")
        else:
            logger.error("✗ Neo4j health check failed")
            return 1
        
        # Get statistics
        stats = neo4j_client.get_statistics()
        logger.info(f"✓ Neo4j initialized - {stats}")
        
        neo4j_client.close()
        return 0
    
    except Exception as e:
        logger.error(f"Error initializing Neo4j: {e}")
        neo4j_client.close()
        return 1

if __name__ == "__main__":
    sys.exit(main())
