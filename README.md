# OSINT Intelligence Platform

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
- **Kibana** - Data visualization (optional)

## Features

### Input Analysis
- Automatic input type detection (email, username, domain, person name, phone, URL, IP, hash)
- Confidence scoring (0.0-1.0) for classification
- Extraction of secondary indicators from input

### OSINT Modules

**Multi-Purpose Gatherers (MPG):**
- Search Engine - Google/DuckDuckGo queries
- Web Spider - HTML content extraction

**Metadata Extractors (MEI):**
- Email extraction from raw content
- Phone number extraction
- Username extraction
- Image URL extraction

**Social Media:**
- Twitter/X profile search
- LinkedIn profile search
- GitHub user/repository search

**Infrastructure:**
- DNS/WHOIS lookup
- Domain intelligence gathering

**Security:**
- Data breach search
- Email verification

### Processing Pipeline

1. **Input Analysis** - Automatic type detection and module routing
2. **Module Execution** - Parallel execution of selected modules
3. **Result Filtering** - Noise removal (HTML attributes, spam, generic domains)
4. **Scoring** - Automatic relevance scoring (0.0-1.0)
5. **Deduplication** - Removal of duplicate findings
6. **Indexing** - Storage in Elasticsearch for fast retrieval

### Search Modes

**Static Mode:**
- Predefined module sets per input type
- Single execution iteration
- Fast and predictable

**Dynamic Mode:**
- Iterative execution (up to 5 iterations)
- Automatic indicator extraction from findings
- Progressive discovery of related information
- Configurable relevance thresholds

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

### Configuration

Environment files in `envs/` directory:

- `api.env` - API service configuration
- `worker.env` - Worker service configuration  
- `worker_dynamic.env` - Dynamic search configuration (optional)

Key settings:
- `DATABASE_URL` - PostgreSQL connection
- `CELERY_BROKER` - Redis connection
- `ELASTICSEARCH_URL` - Elasticsearch endpoint
- `MAX_ITERATIONS` - Maximum search iterations (dynamic mode)
- `MODULE_TIMEOUT_SECONDS` - Per-module timeout

## Usage

### Web Interface

1. Navigate to `http://localhost:8000`
2. Enter search query (email, name, username, etc.)
3. System automatically detects input type
4. View findings in real-time as modules complete
5. Access job history at `/jobs`
6. Check system status at `/system`

### API Endpoints

**Create Search:**
```bash
POST /api/v1/ingest/name
Content-Type: application/json

{
  "value": "search-query",
  "execution_mode": "normal"
}
```

**Get Job Status:**
```bash
GET /api/v1/jobs/{job_id}
```

**List Jobs:**
```bash
GET /api/v1/jobs?limit=20&offset=0
```

**System Health:**
```bash
GET /api/v1/health
```

## Development

### Project Structure

```
services/
├── api/                    # FastAPI service
│   ├── app/
│   │   ├── api/           # Route handlers
│   │   ├── templates/     # Jinja2 templates
│   │   ├── static/        # CSS, JS files
│   │   └── tasks/         # Celery client
│   └── requirements.txt
├── worker/                 # Celery worker
│   ├── tasks/
│   │   ├── modules/       # OSINT modules
│   │   │   ├── base/      # Base classes
│   │   │   ├── mei/       # Metadata extractors
│   │   │   ├── social_media/
│   │   │   ├── infrastructure/
│   │   │   ├── security/
│   │   │   └── utils/     # Input analysis, filtering
│   │   ├── coordinator.py # Task coordination
│   │   └── orchestrator.py
│   └── config/            # Dynamic search config
└── infra/                 # Database initialization
```

### Adding New Modules

1. Create class inheriting from `BaseSearcher`
2. Implement `search()`, `get_supported_types()`, `get_priority()`
3. Register in orchestrator
4. Add to `INDICATOR_MODULE_MAPPING` if needed

### Running Tests

```bash
# Environment verification
python verify_env.py

# Worker container tests
docker-compose exec worker python test_dynamic_search.py
```

### Rebuild Services

```bash
# Rebuild specific service
docker-compose up -d --build api

# Rebuild all services
docker-compose up -d --build
```

## Current Limitations

- No real API credentials configured (modules return mock data)
- Authentication bypassed in development mode
- Limited rate limiting implementation
- No caching layer for repeated queries
- Basic error handling in some modules

## Roadmap

- [ ] Real API integrations (Twitter, LinkedIn, etc.)
- [ ] Advanced caching mechanism
- [ ] Rate limiting per module
- [ ] Result export (JSON, CSV, PDF)
- [ ] Advanced filtering and tagging
- [ ] Scheduled/recurring searches
- [ ] Multi-user support with permissions

## License

MIT License - See LICENSE file for details

## Contributing

1. Fork repository
2. Create feature branch (`git checkout -b feature/name`)
3. Commit changes (`git commit -m 'Add feature'`)
4. Push to branch (`git push origin feature/name`)
5. Open Pull Request

## Security

This platform is intended for legal OSINT research only. Users are responsible for complying with applicable laws and terms of service of data sources.

Report security vulnerabilities to: [security contact]

## Support

- Documentation: [project wiki/docs]
- Issues: GitHub Issues
- Discussions: GitHub Discussions
