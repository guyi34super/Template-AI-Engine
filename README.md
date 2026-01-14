# AI-RAG Document Processing Engine

## Table of Contents

- [Overview](#overview)
- [System Architecture](#system-architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Server](#running-the-server)
- [API Documentation](#api-documentation)
- [Engine Components](#engine-components)
- [File Structure](#file-structure)
- [Production Deployment](#production-deployment)
- [Troubleshooting](#troubleshooting)

---

## Overview

AI-RAG Document Processing Engine is an enterprise-grade platform for document extraction, intelligent data mapping, and LLM-powered data processing. The system provides a unified REST API for processing documents, mapping JSON structures, and managing conversational memory across sessions.

### Key Features

- Multi-format document extraction (PDF, DOCX, XLSX, CSV, TXT, Images)
- LLM-based intelligent field mapping between JSON structures
- PowerMemory engine with session-based memory management
- Chat interface for natural language file operations
- Databricks LLM integration (Meta-Llama models)
- Vector database support via ChromaDB
- Production-ready with environment-based configuration

### Technology Stack

- **Backend Framework**: FastAPI with Uvicorn
- **LLM Integration**: Databricks (Meta-Llama 3.1 8B, Meta-Llama 3.3 70B)
- **Embeddings**: Databricks GTE-Large-EN
- **Vector Database**: ChromaDB with SQLite persistence
- **OCR Engines**: EasyOCR, Docling
- **Document Processing**: PyPDF2, python-docx, openpyxl, pandas
- **Memory Storage**: SQLite (memory_graph.db, sessions.db)

---

## System Architecture

### High-Level Architecture

```
Client Application
       |
       | HTTP/REST
       v
+------------------+
|   FastAPI App    |
|  (api_server.py) |
+------------------+
       |
       +---> Document Extraction Engine
       |       - PDF/Image OCR
       |       - Excel/CSV parsing
       |       - DOCX text extraction
       |
       +---> Mapping Engine
       |       - JSON structure analysis
       |       - LLM-based field mapping
       |       - Schema transformation
       |
       +---> PowerMemory Engine
       |       - Session management
       |       - File structure caching
       |       - SHA-256 hashing
       |       - SQLite storage
       |
       +---> Chat Engine
               - Natural language processing
               - File manipulation
               - Conversational interface
```

### Data Flow

1. **Document Upload**: Files uploaded via multipart/form-data
2. **Extraction**: Content extracted using appropriate parser (OCR, text, structured)
3. **Processing**: LLM processes extracted content based on endpoint
4. **Storage**: Results saved to output directories, memories stored in SQLite
5. **Response**: JSON response with processing results and file paths

---

## Installation

### Prerequisites

- Python 3.9 or higher (tested with Python 3.13)
- Databricks workspace with LLM endpoints
- Minimum 4GB RAM
- 10GB free disk space
- Windows, Linux, or macOS

### Setup Steps

1. **Clone or download the repository**

2. **Navigate to the project directory**
   ```bash
   cd ai-engine
   ```

3. **Install Python dependencies**
   ```bash
   pip install -r requirements-api.txt
   ```

4. **Create environment configuration**
   ```bash
   # Windows
   copy .env.example .env
   
   # Linux/Mac
   cp .env.example .env
   ```

5. **Edit .env file with your credentials**
   
   Open `.env` in a text editor and configure the required variables (see Configuration section below).

---

## Configuration

### Environment Variables

The system uses a `.env` file for configuration. All settings are loaded via `core/env_config.py`.

#### Required Variables

```env
# Databricks API Configuration
DATABRICKS_TOKEN=dapi1234567890abcdef
DATABRICKS_SMALL_LLM_ENDPOINT=databricks-meta-llama-3-1-8b-instruct
DATABRICKS_LARGE_LLM_ENDPOINT=databricks-meta-llama-3-3-70b-instruct
DATABRICKS_EMBEDDING_ENDPOINT=databricks-gte-large-en
```

**How to obtain Databricks credentials:**
1. Log in to your Databricks workspace
2. Navigate to User Settings > Access Tokens
3. Generate a new token
4. Note your serving endpoint names from the Models section

#### Optional Variables

```env
# Server Configuration
HOST=0.0.0.0
PORT=8000
RELOAD=false

# LLM Parameters
MAX_TOKENS=8000
TEMPERATURE=0.1

# Logging
LOG_LEVEL=INFO

# Paths (relative to project root)
UPLOAD_FOLDER=output/uploads
OUTPUT_FOLDER=output/extract
JSON_OUTPUT_FOLDER=output/json
API_OUTPUT_FOLDER=output/api
CHAT_UPLOAD_FOLDER=output/chat/uploads
MAPPING_OUTPUT_FOLDER=output/mapping
MEMORY_DB_PATH=power_memory/data/memory_graph.db
SESSIONS_DB_PATH=power_memory/data/sessions.db
CHROMA_PERSIST_DIR=data/chroma
```

### Configuration Loading

The `Config` class in `core/env_config.py` automatically:
- Loads variables from `.env` file
- Provides default values for optional settings
- Creates required output directories on startup
- Validates critical configuration

---

## Running the Server

### Method 1: Direct Python Execution

```bash
# Windows
C:\Path\To\Python\python.exe api_server.py

# Linux/Mac
python3 api_server.py
```

### Method 2: Using Startup Scripts

**Windows (start.bat):**
```cmd
start.bat
```

**Linux/Mac (start.sh):**
```bash
chmod +x start.sh
./start.sh
```

### Method 3: Development Mode with Auto-Reload

Set in `.env`:
```env
RELOAD=true
```

Then run:
```bash
python api_server.py
```

### Verify Server Status

Once started, you should see:

```
============================================================
AI-RAG Document Processing Engine
============================================================
Host: 0.0.0.0
Port: 8000
API Docs: http://localhost:8000/docs
============================================================
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**Access Points:**
- API Documentation (Swagger): http://localhost:8000/docs
- Health Check: http://localhost:8000/health
- Alternative API Docs (ReDoc): http://localhost:8000/redoc

---

## API Documentation

### API Organization

The API is organized into four main sections:

1. **Document Extraction** - 11 endpoints for processing documents
2. **Mapping Engine** - 7 endpoints for JSON field mapping
3. **PowerMemory** - 15+ endpoints for memory management
4. **Chat Engine** - 2 endpoints for conversational file operations

### Document Extraction Endpoints

#### POST /extract/direct
Extract structured data from uploaded documents.

**Request:**
```bash
curl -X POST "http://localhost:8000/extract/direct" \
  -F "files=@document.pdf" \
  -F "instruction=Extract all invoice line items"
```

**Response:**
```json
{
  "results": [
    {
      "filename": "document.pdf",
      "extraction": {
        "invoice_number": "INV-001",
        "items": [...]
      },
      "output_file": "output/extract/document_20260114_120000.json"
    }
  ]
}
```

#### POST /extract/optimized
High-performance extraction with caching.

#### POST /extract/batch
Process multiple files in parallel.

#### GET /extract/jobs
List all extraction jobs.

#### GET /extract/jobs/{job_id}
Get status and results of a specific job.

### Mapping Engine Endpoints

#### POST /mapping/analyze-structure
Analyze JSON structure and identify fields.

**Request:**
```bash
curl -X POST "http://localhost:8000/mapping/analyze-structure" \
  -H "Content-Type: application/json" \
  -d '{"data": {"name": "John", "age": 30}}'
```

**Response:**
```json
{
  "structure_analysis": {
    "total_fields": 2,
    "field_types": {"name": "string", "age": "integer"},
    "nested_levels": 1
  }
}
```

#### POST /mapping/suggest-mapping
Generate intelligent field mapping suggestions.

**Request:**
```json
{
  "source": {"first_name": "John", "age": 30},
  "target": {"name": "", "years_old": 0}
}
```

**Response:**
```json
{
  "mappings": [
    {"source_field": "first_name", "target_field": "name", "confidence": 0.95},
    {"source_field": "age", "target_field": "years_old", "confidence": 0.90}
  ]
}
```

#### POST /mapping/map
Execute field mapping transformation.

#### POST /mapping/validate
Validate mapping configuration.

#### POST /mapping/upload-and-map
Upload two JSON files, map them, and save result.

**Request:**
```bash
curl -X POST "http://localhost:8000/mapping/upload-and-map" \
  -F "source_file=@source.json" \
  -F "target_file=@target.json"
```

**Response:**
```json
{
  "status": "success",
  "output_file": "output/mapping/mapped_source_20260114_120000.json",
  "mapping_info": {
    "total_fields_mapped": 15,
    "successful_mappings": 14,
    "failed_mappings": 1
  },
  "field_mappings": [...],
  "transformed_data": {...}
}
```

### PowerMemory Endpoints

#### POST /memory/session
Create a new memory session.

**Request:**
```json
{
  "user_id": "user123",
  "session_name": "Project Alpha"
}
```

**Response:**
```json
{
  "session_id": "sess_abc123",
  "user_id": "user123",
  "created_at": "2026-01-14T12:00:00Z"
}
```

#### POST /memory/session/{session_id}/message
Add a message with memory context.

#### GET /memory/session/{session_id}/history
Retrieve conversation history.

#### POST /memory/cache/file-structure
Cache file structure with SHA-256 hash.

**Request:**
```json
{
  "file_path": "/path/to/file.json",
  "structure": {"fields": ["name", "age"]},
  "session_id": "sess_abc123"
}
```

#### GET /memory/cache/file-structure/{file_hash}
Retrieve cached file structure.

#### DELETE /memory/session/{session_id}
Delete a session and its memories.

#### GET /memory/sessions
List all sessions for a user.

### Chat Engine Endpoints

#### POST /chat/upload
Upload files for chat-based manipulation.

#### POST /chat/query
Query uploaded files using natural language.

**Request:**
```json
{
  "query": "Find all records where age > 30",
  "session_id": "sess_abc123"
}
```

---

## Engine Components

### 1. Document Extraction Engine

**Location:** `extractors/`, `pipelines/extract_flow.py`

**Supported Formats:**
- PDF: Docling-based extraction with layout preservation
- Images (PNG, JPG): EasyOCR with GPU acceleration support
- Excel (XLSX): pandas-based structured data extraction
- CSV: Intelligent delimiter detection and parsing
- Word (DOCX): python-docx text extraction
- TXT: UTF-8 text file reading

**Key Features:**
- Automatic format detection
- OCR with multiple engine support
- Table and form recognition
- Batch processing capabilities
- Job queue management

**Files:**
- `extractors/pdf/main_pdf.py` - PDF extraction logic
- `extractors/easyocr/easyocr_extractor.py` - OCR engine
- `extractors/docling/main.py` - Advanced PDF processing
- `pipelines/extract_flow.py` - Extraction orchestration

### 2. Mapping Engine

**Location:** `mapping_engine/`

**Functionality:**
- JSON structure analysis and field identification
- LLM-powered field mapping with confidence scores
- Semantic similarity matching using embeddings
- Schema transformation and validation
- Support for nested objects and arrays

**Key Components:**
- `engine.py` - Core mapping logic and LLM integration
- `prompts.py` - Prompt templates for mapping tasks
- `models.py` - Pydantic models for request/response validation
- `api_routes.py` - FastAPI endpoints

**Mapping Algorithm:**
1. Analyze source and target JSON structures
2. Extract field names, types, and sample values
3. Generate embeddings for semantic comparison
4. Use LLM to suggest mappings with confidence scores
5. Transform source data to target schema
6. Validate and return mapped result

### 3. PowerMemory Engine

**Location:** `power_memory/`

**Architecture:**
- **Session Management:** Multi-user, multi-session support
- **Memory Storage:** SQLite database (memory_graph.db)
- **Caching:** SHA-256 hash-based file structure caching
- **Global Cache:** In-memory cache for frequently accessed data

**Database Schema:**

**sessions table:**
```sql
CREATE TABLE sessions (
  session_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  created_at TIMESTAMP,
  last_active TIMESTAMP
)
```

**memories table:**
```sql
CREATE TABLE memories (
  memory_id TEXT PRIMARY KEY,
  session_id TEXT,
  content TEXT,
  memory_type TEXT,
  timestamp TIMESTAMP,
  metadata JSON
)
```

**file_cache table:**
```sql
CREATE TABLE file_cache (
  file_hash TEXT PRIMARY KEY,
  file_path TEXT,
  structure JSON,
  cached_at TIMESTAMP,
  session_id TEXT
)
```

**Features:**
- Persistent memory across sessions
- Fast file structure retrieval via hashing
- Automatic cache invalidation
- Memory pruning for performance

**Files:**
- `engine.py` - PowerMemory core engine
- `db_manager.py` - Database operations
- `cache_manager.py` - Caching logic
- `api_routes.py` - API endpoints

### 4. Chat Engine

**Location:** `chat_engine/`

**Capabilities:**
- Natural language file querying
- Data filtering and transformation
- File manipulation commands
- Conversational context management

**Processing Flow:**
1. User uploads files to chat session
2. Files parsed and indexed
3. User sends natural language query
4. LLM interprets query and generates operations
5. Operations executed on file data
6. Results returned in natural language + JSON

**Files:**
- `chat_handler.py` - Query processing logic
- `json_manager.py` - JSON file operations
- `api_routes.py` - API endpoints

### 5. Core Utilities

**Location:** `core/`

**Components:**

**env_config.py** - Environment configuration management
- Loads `.env` file
- Provides Config class with all settings
- Creates output directories automatically

**llm.py** - Databricks LLM client
- Chat completion interface
- Streaming support
- Error handling and retries

**embeddings.py** - Embedding generation
- Text-to-vector conversion
- Batch processing support
- Databricks embedding endpoint integration

**vdb.py** - Vector database operations
- ChromaDB wrapper
- Collection management
- Similarity search

**models.py** - Data models
- Pydantic schemas for validation
- Request/response models

**hashing.py** - File hashing utilities
- SHA-256 hash generation
- File change detection

---

## File Structure

```
ai-engine/
│
├── .env                          # Environment configuration (create from .env.example)
├── .env.example                  # Environment template
├── .gitignore                    # Git ignore rules
├── requirements-api.txt          # Python dependencies
├── api_server.py                 # Main FastAPI application
├── main.py                       # Legacy entry point
├── start.bat                     # Windows startup script
├── start.sh                      # Linux/Mac startup script
│
├── core/                         # Core utilities and configuration
│   ├── env_config.py            # Environment variable loader and Config class
│   ├── config.py                # Legacy configuration (uses env_config)
│   ├── llm.py                   # Databricks LLM client
│   ├── embeddings.py            # Embedding generation
│   ├── vdb.py                   # Vector database (ChromaDB)
│   ├── models.py                # Pydantic data models
│   ├── hashing.py               # SHA-256 file hashing
│   ├── security.py              # Security utilities
│   ├── templates.py             # Template management
│   └── [other core modules]
│
├── extractors/                   # Document extraction modules
│   ├── pdf/
│   │   ├── main_pdf.py          # PDF extraction logic
│   │   └── adapter.py           # PDF adapter interface
│   ├── docling/
│   │   └── main.py              # Advanced PDF processing (Docling)
│   ├── easyocr/
│   │   ├── easyocr_extractor.py # OCR extraction engine
│   │   └── models/              # OCR model files
│   ├── csv.py                   # CSV file parser
│   ├── xlsx.py                  # Excel file parser
│   ├── docx.py                  # Word document parser
│   └── txt.py                   # Text file reader
│
├── mapping_engine/               # Intelligent field mapping
│   ├── engine.py                # Core mapping logic
│   ├── prompts.py               # LLM prompt templates
│   ├── models.py                # Mapping data models
│   └── api_routes.py            # Mapping API endpoints
│
├── power_memory/                 # Memory management engine
│   ├── engine.py                # PowerMemory core engine
│   ├── db_manager.py            # SQLite database operations
│   ├── cache_manager.py         # File structure caching
│   ├── api_routes.py            # Memory API endpoints
│   └── data/
│       ├── memory_graph.db      # Memory storage database
│       └── sessions.db          # Session management database
│
├── chat_engine/                  # Conversational file operations
│   ├── chat_handler.py          # Query processing
│   ├── json_manager.py          # JSON operations
│   ├── hash_protector.py        # File integrity checking
│   └── api_routes.py            # Chat API endpoints
│
├── pipelines/                    # Processing pipelines
│   ├── extract_flow.py          # Document extraction pipeline
│   ├── ingest.py                # Data ingestion pipeline
│   └── classify_headers.py      # Header classification
│
├── scripts/                      # Utility scripts
│   ├── seed_docs.py             # Seed sample documents
│   ├── seed_templates.py        # Seed templates
│   └── build_registry_and_seed.py
│
├── data/                         # Data storage
│   └── chroma/                  # ChromaDB vector database
│       └── chroma.sqlite3       # Vector storage
│
├── output/                       # Generated outputs
│   ├── uploads/                 # Uploaded files
│   ├── extract/                 # Extracted data (JSON/JSONL)
│   ├── json/                    # Processed JSON files
│   ├── api/                     # API operation results
│   ├── mapping/                 # Mapped JSON files
│   ├── chat/
│   │   ├── uploads/            # Chat uploaded files
│   │   └── modified/           # Chat modified files
│   ├── raw_extraction/          # Raw text extractions
│   └── logs/                    # Application logs
│
└── templates/                    # Template files
    ├── registry.json            # Template registry
    └── seed/                    # Seed templates

```

### Key Files Explained

**api_server.py**
- Main FastAPI application
- Registers all routers (extraction, mapping, memory, chat)
- Configures CORS, middleware
- Health check endpoint
- Loads configuration from core/env_config.py

**core/env_config.py**
- Centralized configuration management
- Loads .env file and provides Config class
- Default values for all settings
- Creates output directories on import

**.env**
- Environment-specific configuration
- Contains sensitive credentials (not committed to git)
- Created from .env.example template

**power_memory/data/*.db**
- SQLite databases for memory storage
- memory_graph.db: User memories and conversations
- sessions.db: Session metadata and cache

**output/**
- All generated files stored here
- Automatically created by Config.ensure_directories()
- Subdirectories for different output types

---

## Production Deployment

### Prerequisites for Production

1. **Secure Credentials**
   - Use strong Databricks API tokens
   - Rotate tokens regularly
   - Never commit .env to version control

2. **Server Configuration**
   - Set `RELOAD=false` in production
   - Configure `LOG_LEVEL=INFO` or `WARNING`
   - Use reverse proxy (Nginx, Apache)
   - Enable HTTPS/TLS

3. **Resource Allocation**
   - Minimum 4GB RAM
   - 20GB+ disk space for output files
   - Multi-core CPU for parallel processing

### Deployment Options

#### Option 1: Systemd Service (Linux)

Create `/etc/systemd/system/ai-rag-engine.service`:

```ini
[Unit]
Description=AI-RAG Document Processing Engine
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/ai-engine
Environment="PATH=/usr/bin:/usr/local/bin"
EnvironmentFile=/opt/ai-engine/.env
ExecStart=/usr/bin/python3 /opt/ai-engine/api_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Commands:
```bash
sudo systemctl daemon-reload
sudo systemctl enable ai-rag-engine
sudo systemctl start ai-rag-engine
sudo systemctl status ai-rag-engine
```

#### Option 2: Docker Deployment

Create `Dockerfile`:

```dockerfile
FROM python:3.13-slim

WORKDIR /app

COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

COPY . .

EXPOSE 8000

CMD ["python", "api_server.py"]
```

Build and run:
```bash
docker build -t ai-rag-engine .
docker run -d \
  --name ai-rag-engine \
  -p 8000:8000 \
  --env-file .env \
  -v $(pwd)/output:/app/output \
  -v $(pwd)/data:/app/data \
  ai-rag-engine
```

#### Option 3: PM2 Process Manager

Install PM2:
```bash
npm install -g pm2
```

Create `ecosystem.config.js`:
```javascript
module.exports = {
  apps: [{
    name: 'ai-rag-engine',
    script: 'api_server.py',
    interpreter: 'python3',
    cwd: '/opt/ai-engine',
    env: {
      NODE_ENV: 'production'
    },
    error_file: './output/logs/pm2-error.log',
    out_file: './output/logs/pm2-out.log',
    log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
  }]
};
```

Commands:
```bash
pm2 start ecosystem.config.js
pm2 save
pm2 startup
```

#### Option 4: Windows Service

Use NSSM (Non-Sucking Service Manager):

```cmd
nssm install AIRagEngine "C:\Python313\python.exe" "C:\ai-engine\api_server.py"
nssm set AIRagEngine AppDirectory "C:\ai-engine"
nssm set AIRagEngine AppEnvironmentExtra "Path=C:\ai-engine\.env"
nssm start AIRagEngine
```

### Reverse Proxy Configuration

#### Nginx

```nginx
server {
    listen 80;
    server_name api.example.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Increase timeout for long-running operations
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }
}
```

### Load Balancing

For high availability, run multiple instances:

```nginx
upstream ai_rag_backend {
    server localhost:8000;
    server localhost:8001;
    server localhost:8002;
}

server {
    listen 80;
    location / {
        proxy_pass http://ai_rag_backend;
    }
}
```

### Monitoring and Maintenance

**Health Check Endpoint:**
```bash
curl http://localhost:8000/health
```

**Log Monitoring:**
```bash
tail -f output/logs/*.log
```

**Database Maintenance:**
```bash
# Backup databases
cp power_memory/data/*.db ./backups/

# Vacuum databases (optimize)
sqlite3 power_memory/data/memory_graph.db "VACUUM;"
```

**Disk Space Monitoring:**
```bash
du -sh output/*
```

### Security Best Practices

1. **API Authentication**
   - Implement API key middleware in api_server.py
   - Use JWT tokens for user sessions
   - Rate limiting to prevent abuse

2. **File Upload Validation**
   - Restrict file types and sizes
   - Scan uploads for malware
   - Isolate upload processing

3. **Network Security**
   - Use firewall rules to restrict access
   - Enable HTTPS only
   - Set up VPN for internal APIs

4. **Data Protection**
   - Encrypt sensitive data at rest
   - Implement data retention policies
   - Regular backup of databases

---

## Troubleshooting

### Common Issues

#### 1. Server Won't Start

**Problem:** Python not found or wrong version

**Solution:**
```bash
# Check Python version
python --version  # Should be 3.9+

# Use full path if needed (Windows)
C:\Python313\python.exe api_server.py

# Or Python 3 explicitly (Linux/Mac)
python3 api_server.py
```

#### 2. Databricks Connection Error

**Problem:** Authentication failed or endpoint not found

**Solution:**
- Verify `DATABRICKS_TOKEN` in .env is correct
- Check endpoint names match your Databricks workspace
- Test connection:
  ```bash
  curl -H "Authorization: Bearer YOUR_TOKEN" \
    https://your-workspace.databricks.com/api/2.0/clusters/list
  ```

#### 3. Missing Dependencies

**Problem:** Import errors on startup

**Solution:**
```bash
pip install -r requirements-api.txt --upgrade
```

#### 4. Port Already in Use

**Problem:** Error binding to port 8000

**Solution:**
```bash
# Windows - find and kill process
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Linux/Mac
lsof -ti:8000 | xargs kill -9

# Or change port in .env
PORT=8001
```

#### 5. Out of Memory Errors

**Problem:** System runs out of RAM during processing

**Solution:**
- Reduce `MAX_TOKENS` in .env (e.g., 4000 instead of 8000)
- Process fewer files in batch operations
- Increase system RAM
- Enable swap space (Linux)

#### 6. Slow Extraction Performance

**Problem:** Document processing takes too long

**Solution:**
- Use `/extract/optimized` endpoint instead of `/extract/direct`
- Enable caching in PowerMemory
- Reduce image resolution before upload
- Use faster LLM endpoint (small model)

#### 7. ChromaDB Errors

**Problem:** Vector database initialization fails

**Solution:**
```bash
# Delete and recreate ChromaDB
rm -rf data/chroma
mkdir -p data/chroma

# Restart server to reinitialize
```

#### 8. SQLite Database Locked

**Problem:** Database locked errors in PowerMemory

**Solution:**
```bash
# Close all connections and restart server
# Or delete and recreate databases
rm power_memory/data/*.db

# Databases will be recreated on next startup
```

### Getting Help

1. **Check Logs**
   ```bash
   # View recent logs
   ls -lt output/logs/
   
   # Read error logs
   cat output/logs/error.log
   ```

2. **Enable Debug Mode**
   
   In `.env`:
   ```env
   LOG_LEVEL=DEBUG
   ```

3. **Test Individual Components**
   ```bash
   # Test configuration
   python -c "from core.env_config import config; print(config.DATABRICKS_TOKEN[:10])"
   
   # Test LLM connection
   python -c "from core.llm import get_llm_client; client = get_llm_client(); print('LLM OK')"
   
   # Test embeddings
   python -c "from core.embeddings import get_embeddings; emb = get_embeddings(); print('Embeddings OK')"
   ```

4. **Verify File Permissions**
   ```bash
   # Ensure output directories are writable
   chmod -R 755 output/
   chmod -R 755 power_memory/data/
   ```

### Performance Tuning

**For High Throughput:**
```env
MAX_TOKENS=4000
TEMPERATURE=0.0
LOG_LEVEL=WARNING
```

**For High Accuracy:**
```env
MAX_TOKENS=8000
TEMPERATURE=0.1
DATABRICKS_SMALL_LLM_ENDPOINT=databricks-meta-llama-3-3-70b-instruct
```

**For Development:**
```env
RELOAD=true
LOG_LEVEL=DEBUG
MAX_TOKENS=2000
```

---

## License

This project is proprietary software. All rights reserved.

## Support

For technical support or questions, contact your system administrator or refer to internal documentation.

---

**Version:** 1.0.0  
**Last Updated:** January 14, 2026  
**Python Version:** 3.9+  
**Framework:** FastAPI 0.100+
├── power_memory/            # Memory management
│   ├── engine.py            # Memory orchestrator
│   ├── stores/              # SQLite storage
│   ├── services/            # Chunking, extraction
│   └── api_routes.py        # API endpoints
│
├── chat_engine/             # Natural language ops
│   ├── chat_handler.py      # Query processor
│   └── api_routes.py        # API endpoints
│
├── output/                  # Generated files
│   ├── extract/            # Extraction results
│   ├── mapping/            # Mapped files
│   └── chat/               # Chat modifications
│
└── api_server.py           # Main FastAPI application
```

---

## API Endpoints

### Document Extraction

Extract structured data from documents.

```bash
# Upload file for extraction
POST /extract/upload
Content-Type: multipart/form-data

# Get extraction result
GET /extract/jobs/{job_id}

# List all jobs
GET /extract/list
```

**Supported Formats**: PDF, PNG, JPG, XLSX, XLS, CSV, DOCX, TXT

### Mapping Engine

Intelligent field mapping between JSON structures.

```bash
# Map JSON fields
POST /mapping/map-fields
{
  "source_json": [{"first_name": "John", "email_address": "john@example.com"}],
  "target_schema": ["FirstName", "Email", "Phone"]
}

# Upload and map files
POST /mapping/upload-and-map
Form-data:
  - source_file: source.json
  - target_file: target.json

# Quick field mapping
POST /mapping/quick-map
{
  "source_fields": ["first_name", "email_address"],
  "target_fields": ["FirstName", "Email"]
}
```

**Strategies**: AUTO (LLM), MANUAL (user-defined), HYBRID (both)

### PowerMemory

Multi-session memory and file caching.

```bash
# Create session
POST /memory/session/create
{"user_id": "user123"}

# Add message
POST /memory/session/message
{"session_id": "sess_001", "role": "user", "content": "..."}

# Search memories
POST /memory/memories/search
{"query": "payroll data", "user_id": "user123"}

# Analyze file structure
POST /memory/file/analyze
{"file_path": "data.json", "data": [...]}
```

### Chat Engine

Natural language file manipulation.

```bash
# Upload and modify with query
POST /chat/upload-and-modify
Form-data:
  - file: data.json
  - query: "Add overtime column after hours"
```

---

## Usage Examples

### Example 1: Extract PDF

```python
import requests

# Upload PDF
with open("invoice.pdf", "rb") as f:
    response = requests.post(
        "http://localhost:8000/extract/upload",
        files={"file": f}
    )

job_id = response.json()["job_id"]

# Get results
result = requests.get(f"http://localhost:8000/extract/jobs/{job_id}")
print(result.json()["extracted_data"])
```

### Example 2: Map Fields

```python
import requests

response = requests.post(
    "http://localhost:8000/mapping/quick-map",
    json={
        "source_fields": ["emp_id", "fname", "lname"],
        "target_fields": ["EmployeeNumber", "FirstName", "LastName"]
    }
)

mappings = response.json()["mappings"]
for m in mappings:
    print(f"{m['source_field']} → {m['target_field']} ({m['confidence']})")
```

### Example 3: Upload and Map Files

```bash
curl -X POST "http://localhost:8000/mapping/upload-and-map" \
  -F "source_file=@payroll_data.json" \
  -F "target_file=@payroll_schema.json" \
  -F "strategy=auto"
```

Output saved to: `output/mapping/mapped_payroll_data_YYYYMMDD_HHMMSS.json`

---

## Configuration Reference

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABRICKS_TOKEN` | Databricks API token | *Required* |
| `DATABRICKS_SMALL_LLM_ENDPOINT` | Small LLM endpoint | *Required* |
| `DATABRICKS_EMBEDDING_ENDPOINT` | Embedding endpoint | *Required* |
| `HOST` | Server host | `0.0.0.0` |
| `PORT` | Server port | `8000` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `MAX_TOKENS` | Max LLM tokens | `8000` |
| `TEMPERATURE` | LLM temperature | `0.1` |

### Directory Structure

| Directory | Purpose |
|-----------|---------|
| `output/extract/` | Extraction results (JSON/JSONL) |
| `output/mapping/` | Mapped files |
| `output/chat/` | Chat-modified files |
| `data/chroma/` | Vector database |
| `power_memory/data/` | Memory databases |

---

## Production Deployment

### Using Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir -r requirements-api.txt

EXPOSE 8000

CMD ["python", "api_server.py"]
```

```bash
# Build
docker build -t ai-rag-engine .

# Run
docker run -p 8000:8000 --env-file .env ai-rag-engine
```

### Using Systemd (Linux)

```ini
[Unit]
Description=AI-RAG Engine API
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/ai-rag-engine
EnvironmentFile=/opt/ai-rag-engine/.env
ExecStart=/usr/bin/python3 api_server.py
Restart=always

[Install]
WantedBy=multi-user.target
```

### Using PM2 (Node.js)

```bash
pm2 start api_server.py --name ai-rag --interpreter python3
pm2 save
pm2 startup
```

---

## Performance Optimization

### Recommended Settings

**For High Volume:**
```env
MAX_TOKENS=4000
TEMPERATURE=0.0
```

**For Accuracy:**
```env
MAX_TOKENS=8000
TEMPERATURE=0.1
```

### Caching

PowerMemory automatically caches:
- File structures (global across users)
- LLM responses
- Extraction patterns

### Resource Requirements

| Workload | CPU | RAM | Storage |
|----------|-----|-----|---------|
| Light | 2 cores | 4GB | 10GB |
| Medium | 4 cores | 8GB | 50GB |
| Heavy | 8+ cores | 16GB+ | 100GB+ |

---

## Troubleshooting

### Common Issues

**1. Import Error**
```bash
# Install missing dependencies
pip install -r requirements-api.txt
```

**2. Port Already in Use**
```bash
# Change port in .env
PORT=8001
```

**3. Databricks Connection Failed**
```bash
# Verify credentials
echo $DATABRICKS_TOKEN
# Check endpoint in .env
```

**4. Out of Memory**
```bash
# Reduce max tokens
MAX_TOKENS=4000
```

### Logs

Check logs for errors:
```bash
# View console output
python api_server.py

# Or redirect to file
python api_server.py > api.log 2>&1
```

---

## Development

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run tests
pytest tests/
```

### Code Style

```bash
# Format code
black .

# Lint
flake8 .
```

---

## API Authentication (Optional)

Add API key authentication:

```python
# In api_server.py
from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader

API_KEY = os.getenv("API_KEY", "your-secret-key")
api_key_header = APIKeyHeader(name="X-API-Key")

async def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key

# Add to endpoints
@app.post("/extract/upload", dependencies=[Depends(verify_api_key)])
```

---

## Monitoring

### Health Check

```bash
GET /health
```

Returns system status and component health.

### Metrics

Access metrics at: `http://localhost:8000/metrics` (if enabled)

---

## License

Proprietary - Ceridian HCM Inc.

---

## Support

**Issues**: Create an issue in the repository  
**Documentation**: http://localhost:8000/docs (Swagger UI)  
**Version**: 1.0.0

---

## Changelog

### v1.0.0 (2026-01-14)
- ✅ Document extraction (PDF, images, Excel, CSV, DOCX, TXT)
- ✅ Intelligent mapping engine with LLM
- ✅ PowerMemory with global caching
- ✅ Chat-based file manipulation
- ✅ Production-ready configuration
- ✅ Comprehensive API documentation

---

## Quick Command Reference

```bash
# Start server
python api_server.py

# With custom port
PORT=8001 python api_server.py

# View API docs
http://localhost:8000/docs

# Test health
curl http://localhost:8000/health

# Extract file
curl -X POST "http://localhost:8000/extract/upload" \
  -F "file=@document.pdf"

# Map fields
curl -X POST "http://localhost:8000/mapping/quick-map" \
  -H "Content-Type: application/json" \
  -d '{"source_fields":["name"],"target_fields":["Name"]}'
```

---

**Built with FastAPI, Databricks LLM, and EasyOCR** 🚀
