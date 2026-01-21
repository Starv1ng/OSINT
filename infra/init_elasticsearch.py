"""
Initialize Elasticsearch indices for OSINT v2.0
Run this script to create all required indices with proper mappings
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services'))

from shared.elasticsearch_client import ElasticsearchClient
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Initialize Elasticsearch indices"""
    # Connect to Elasticsearch
    es_client = ElasticsearchClient(hosts=["http://localhost:9200"])
    
    logger.info("Creating Elasticsearch indices...")
    
    try:
        es_client.create_indices()
        logger.info("✓ Successfully created indices")
        
        # Verify indices
        if es_client.health_check():
            logger.info("✓ Elasticsearch health check passed")
        else:
            logger.error("✗ Elasticsearch health check failed")
            return 1
        
        # Get index stats
        for index_name in [es_client.findings_index, es_client.module_runs_index]:
            stats = es_client.get_index_stats(index_name)
            if stats:
                logger.info(f"✓ Index {index_name} created successfully")
            else:
                logger.warning(f"✗ Could not get stats for {index_name}")
        
        return 0
    
    except Exception as e:
        logger.error(f"Error initializing Elasticsearch: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
