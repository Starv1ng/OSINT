# OSINT Intelligence Platform (Version Beta 0.01)

## Description

Distributed OSINT (Open Source Intelligence) platform with microservices architecture for automated information gathering and analysis from open sources.

## Architecture

The system consists of the following components:

- **API Service** (FastAPI) - REST gateway and web interface
- **Worker Service** (Celery) - Asynchronous task execution
- **PostgreSQL** - Job storage and status tracking
- **Redis** - Message broker for task queue
- **Elasticsearch** - Finding indexing and search
- **MinIO** - File and artifact storage
- **Neo4j** - Relationship and entity graph

## Features

### Input Analysis (working on it)
- Automatic input type detection (email, username, domain, person name, phone, URL, IP, hash)
- Confidence scoring (0.0-1.0) for classification
- Extraction of secondary indicators from input

## Installation

### Prerequisites
- Docker 20.10+
- Docker Compose 2.0+
- 8GB RAM minimum
- 20GB free disk space

### Quick Start

```bash
# Clone repository
git clone https://github.com/Starv1ng/OSINT.git
cd OSINT

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f api worker

# Access web interface
# http://localhost:8000
```

## Current Limitations

- No real API credentials configured (modules return mock data)
- Authentication bypassed in development mode
- Limited rate limiting implementation
- No caching layer for repeated queries
- Basic error handling in some modules

## Contributing

1. Fork repository
2. Create feature branch (`git checkout -b feature/name`)
3. Commit changes (`git commit -m 'Add feature'`)
4. Push to branch (`git push origin feature/name`)
5. Open Pull Request

## Security

This platform is intended for legal OSINT research only. Users are responsible for complying with applicable laws and terms of service of data sources.

