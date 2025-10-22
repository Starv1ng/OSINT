# 🔍 OSINT Project

## ✅ What Works RIGHT NOW?

- **🐳 Docker Compose** - Everything containerized
- **🚀 FastAPI** - REST endpoints at `http://localhost:8000`
- **🗄️ PostgreSQL** - Database with `jobs` table (testing)
- **🔐 Authentication** - Basic token system
- **📊 Endpoints**:
  - `GET /` - Welcome message
  - `GET /api/v1/health` - System status
  - `GET /api/v1/test-db` - Database connection test
  - `POST /api/v1/ingest/name` - Create OSINT search (framework)

### Current Status

**Foundation Complete - Ready for OSINT Module Development**

The infrastructure is fully operational and can accept search requests. The system is prepared for integrating actual OSINT data collection modules.

## Quick Start

### Prerequisites:
- 🐳 **Docker** and **Docker Compose**
- 📦 **Git**


### Installation and execution:
```bash
# 1. Clone the project
git clone https://github.com/Starv1ng/osint-mvp.git
cd osint-mvp

# 2. Run (everything installs automatically)
docker compose up --build

# 3. Test in your browser
# Open: http://localhost:8000
