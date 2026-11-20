# UbuntuBiz Backend

Production-oriented backend operating system for South African informal businesses, particularly spaza shops and small township retailers.

---

## 1. Project Overview & Architecture

UbuntuBiz provides APIs for spaza operations, inventory, cash flow, rule-based agent workflows, and collaborative bulk buying. Blockchain network and contract settings are configurable; current deployment status must be verified independently.

### Technology Stack

- **Framework:** Python 3.12+, FastAPI, Pydantic v2
- **Database & Storage:** PostgreSQL with tenant RLS policies, SQLite for local testing, SQLAlchemy 2.1, Alembic
- **Blockchain:** Web3.py and configurable Avalanche Fuji C-Chain integration; deployment evidence is not included
- **AI:** Rule-based agent routing and in-process tool servers; no Gemini execution is currently connected
- **Background Workers:** Redis, Celery background worker & scheduler

---

## 2. Implementation Status by Phase

- [x] **PHASE 1: Backend Foundation & Architecture**
  - Project scaffold in `ubuntubiz-backend/`
  - FastAPI application with CORS, request logging, and health checks (`/health`, `/api/health`)
  - Multi-tenant architecture with PostgreSQL RLS support and request-bound context (`app/core/tenant.py`)
  - Core database schema and models (`businesses`, `users`, `audit_log`, `inventory_events`, `stock_levels`, etc.)
  - Alembic migrations (`alembic.ini`, `app/database/migrations/`)
  - Authentication & Authorization: JWT access & refresh tokens, password hashing, PIN login for fast spaza counters
  - Tests for authentication, token revocation, CORS, and tenant-scoped business reads (`tests/test_phase1_auth_and_tenant.py`)

- [x] **PHASE 2: Business Operations & Event Ledger**
  - Product catalog management with colloquial township aliases (`bread`, `isinkwa`, etc.)
  - Append-only immutable inventory event ledger (`inventory_events`) with strict idempotency
  - Atomic stock level updates with negative stock protection
  - Compensating reversal event undo workflow (`/api/inventory/undo/{event_id}`)
  - Financial data tracked in integer cents (e.g. 1500 cents = R15.00)
  - Sales service & REST API (`/api/sales`, `/api/sales/summary`)
  - Expense tracking & cash flow reporting (`/api/expenses`)
  - Tests for inventory, sales, reversals, expenses, and duplicate-sale retries (`tests/test_phase2_inventory_and_sales.py`)

- [x] **PHASE 3: Blockchain Integration (Avalanche Fuji)**
  - Web3.py provider configured for Avalanche Fuji C-Chain (Chain ID `43113`, RPC: `https://api.avax-test.network/ext/bc/C/rpc`)
  - Configurable contract wrapper and ABI input-signature validation (`app/blockchain/abi/UbuntuBiz.json`)
  - Non-custodial transaction verification (`/api/blockchain/verify-transaction`) for user-signed Core Wallet transactions
  - Event decoders and synchronization with PostgreSQL (`SaleRecorded`, `PoolCreated`, `PoolJoined`, `OrderCreated`, `OrderApproved`)
  - Idempotency and deduplication on transactions and event identifiers
  - Mocked-provider tests only; no live deployment verification (`tests/test_phase3_blockchain.py`)

- [x] **PHASE 4: Analytics Automation & Scheduled Jobs**
  - Daily metrics computation: daily sales, gross profit, total expenses, cash variance (`app/services/analytics_service.py`)
  - Automated alert engine: low-stock risk, sales drops (<60% weekday median), alert capping per business
  - Stock health analysis: 30-day velocity, days of stock remaining, dead stock detection
  - Morning business brief generator with factual narrative
  - Celery tasks and beat schedule (`app/jobs/tasks.py`, `app/core/celery_config.py`)
  - Analytics REST APIs (`/api/analytics/summary`, `/api/analytics/daily`, `/api/analytics/profit`, `/api/analytics/stock`, `/api/analytics/alerts`, `/api/analytics/morning-brief`)
  - Offline analytics tests (`tests/test_phase4_analytics.py`)

- [x] **PHASE 5: Multi-Agent AI Architecture & MCP Servers**
  - In-process tool servers and rule-based agent routing
  - 7 Specialized AI Agents: `Orchestrator`, `Capture`, `Inventory`, `Analytics`, `Procurement`, `Policy & Approval`, `Verification`
  - Human-in-the-loop owner approval flow (`/api/approvals`, `/api/approvals/{id}/decide`) with PIN protection for operations >= R500
  - Strict security guardrails: prompt injection neutralization, tool allowlist enforcement, server-derived tenant context
  - Agent tracing and auditability (`agent_tasks`, `agent_tool_calls`, `/api/ai/tasks/{id}/trace`)
  - Conversational AI endpoint (`/api/ai/chat`)
  - Offline policy and approval tests (`tests/test_phase5_ai_and_mcp.py`)

- [ ] **PHASE 6: RAG Knowledge Base & Procurement Workflows** (partial; lexical retrieval only)
- [ ] **PHASE 7: Messaging & Web Chat Simulator** (signed inbound webhook and authenticated web chat; outbound WhatsApp not connected)
- [ ] **PHASE 8: Testing, Seed Data, Docker & Deployment Readiness**

---

## 3. Quick Start & Local Setup

Follow these instructions to run the UbuntuBiz API locally on Windows.

### Prerequisites

Make sure you have:

- Python 3.12 or later
- Git
- A terminal such as Git Bash or Windows PowerShell
- The project dependencies listed in `requirements.txt`

### Step 1: Open the Backend Project

Navigate to the backend root directory:

```bash
cd ~/OneDrive/Desktop/ubuntubiz-backend-full
```

All commands below should be executed from this directory.

### Step 2: Create a Virtual Environment

Create an isolated Python environment for the project:

```bash
python -m venv venv
```

### Step 3: Activate the Virtual Environment

**Git Bash:**

```bash
source venv/Scripts/activate
```

**Windows PowerShell:**

```powershell
.\venv\Scripts\Activate.ps1
```

Once activated, your terminal should display `(venv)` before the directory path.

### Step 4: Install Dependencies

Upgrade pip:

```bash
python -m pip install --upgrade pip
```

Install all backend dependencies:

```bash
python -m pip install -r requirements.txt
```

If you have not yet created a `requirements.txt` file, install the essential API dependencies:

```bash
python -m pip install fastapi "uvicorn[standard]"
```

The full requirements file should contain all dependencies used by the application, including database, authentication, blockchain, and AI packages.

### Step 5: Configure Environment Variables

Create your local `.env` file from the example:

**Git Bash:**

```bash
cp .env.example .env
```

**Windows PowerShell:**

```powershell
Copy-Item .env.example .env
```

Open `.env` and configure the required environment variables, including:

- Database connection details
- JWT secret key and authentication settings
- Avalanche Fuji RPC configuration
- Redis connection details, if required

For local development, a random per-process JWT key is generated when `SECRET_KEY` is omitted. Before production or Docker Compose, configure a randomly generated `SECRET_KEY` of at least 32 characters and a strong PostgreSQL password. Compose also requires an explicit PostgreSQL `DATABASE_URL` pointing to the non-superuser application role; URL-encode special characters in connection credentials. Gemini and WhatsApp values are optional and are not needed for local tests. Never commit your actual `.env` file or expose API keys and private keys in source control.

Docker Compose starts PostgreSQL, Redis, a one-shot migration service, the API, a Celery worker, and Celery Beat. Set `DATABASE_URL` to use Compose's `postgres` hostname. The PostgreSQL init script demotes the configured database role only when the data volume is first initialized; an existing volume is not changed by that script and must have its role privileges reviewed separately before relying on row-level security.

### Step 6: Run Database Migrations

If your environment uses Alembic migrations, apply them before starting the application:

```bash
python -m alembic upgrade head
```

Ensure your configured database is running and accessible before executing this command.

### Step 7: Run Automated Tests

Run the complete test suite:

```bash
python -m pytest tests/ -v
```

To run an individual phase:

```bash
python -m pytest tests/test_phase1_auth_and_tenant.py -v
```

### Step 8: Start the FastAPI Server

Start the local development server:

```bash
python -m uvicorn app.main:app --reload --port 8000
```

The `--reload` option automatically restarts the server whenever you modify application code.

Once the server starts successfully, the API will be available at:

**Base URL:** http://127.0.0.1:8000

**Interactive Swagger documentation:** http://127.0.0.1:8000/api/docs

**ReDoc documentation:** http://127.0.0.1:8000/api/redoc

**Health check:** http://127.0.0.1:8000/health

**API health check:** http://127.0.0.1:8000/api/health

**Database readiness check:** http://127.0.0.1:8000/ready

### Step 9: Stop the Server

To stop the development server, press:

```text
CTRL + C
```

To leave the virtual environment:

```bash
deactivate
```

---

## 4. Common Setup Issues

| Error | Solution |
|---|---|
| `uvicorn: command not found` | Activate the virtual environment and install `uvicorn[standard]`. |
| `No module named 'fastapi'` | Run `python -m pip install fastapi`. |
| `pytest: command not found` | Install pytest using `python -m pip install pytest`. |
| `No module named ...` | Install the missing dependency or reinstall `requirements.txt`. |
| Database connection refused | Check that PostgreSQL is running and the `.env` database settings are correct. |
| Environment variables missing | Confirm that `.env` exists and contains the required configuration. |

**Important:** Always activate the virtual environment before installing dependencies, running tests, or starting the API. Prefer `python -m pip`, `python -m pytest`, and `python -m uvicorn` to avoid Windows PATH issues.

---

## 5. Development Progress

| Phase | Description | Status |
|---|---|---|
| Phase 1 | Backend Foundation & Architecture | Implemented; deployment verification required |
| Phase 2 | Business Operations & Event Ledger | Implemented; deployment verification required |
| Phase 3 | Blockchain Integration | Mock-tested; deployment verification required |
| Phase 4 | Analytics Automation & Scheduled Jobs | Implemented; worker operation not verified |
| Phase 5 | Agent Routing & MCP Tools | Rule-based; Gemini integration not implemented |
| Phase 6 | RAG Knowledge Base & Procurement Workflows | Partial |
| Phase 7 | Messaging & Web Chat Simulator | Partial; no outbound WhatsApp integration |
| Phase 8 | Testing, Seed Data, Docker & Deployment Readiness | Pending |

---

**UbuntuBiz Backend — Building smarter operations and collaborative purchasing for South African small businesses.**