# Voice2Gov Backend API

Civic Complaint Management Platform - Backend Service

## Technology Stack

- **Framework**: FastAPI 0.109+
- **Database**: MongoDB (PyMongo Async 4.6+)
- **Validation**: Pydantic 2.5+
- **Authentication**: JWT (RS256/HS256) with refresh token rotation
- **Testing**: pytest + pytest-asyncio + httpx

## Architecture

```
app/
├── api/v1/           # API routes (health, auth, complaints, etc.)
├── core/             # Configuration, settings
├── db/               # Database connection, indexes
├── exceptions/       # Exception hierarchy, handlers
├── schemas/          # Pydantic models
├── services/         # Business logic (future)
├── repositories/     # Data access (future)
└── main.py           # FastAPI application factory
```

## Quick Start

### Prerequisites

- Python 3.11+
- MongoDB 7.0+
- pip/uv

### Installation

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your configuration
```

### Run Development Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Create Database Indexes

```bash
python scripts/create_indexes.py
```

### Run Tests

```bash
pytest tests/ -v
pytest tests/unit -v
pytest tests/integration -v
```

### Linting

```bash
ruff check .
ruff format .
mypy .
```

## API Endpoints

### Health Checks

- `GET /health` - Liveness probe
- `GET /ready` - Readiness probe (checks MongoDB)

### API Versioning

All endpoints under `/api/v1/`

## Environment Variables

See `.env.example` for all configurable options.

## Project Structure

```
backend/
├── app/
│   ├── api/v1/
│   │   ├── health.py
│   │   └── router.py
│   ├── core/
│   │   └── config.py
│   ├── db/
│   │   └── database.py
│   ├── exceptions/
│   │   ├── base.py
│   │   └── handlers.py
│   ├── schemas/
│   │   ├── base.py
│   │   └── common.py
│   ├── main.py
│   └── ...
├── scripts/
│   └── create_indexes.py
├── tests/
│   ├── unit/
│   │   ├── test_config.py
│   │   ├── test_database.py
│   │   ├── test_health.py
│   │   └── test_exceptions.py
│   └── integration/
├── requirements.txt
├── pyproject.toml
└── .env.example
```