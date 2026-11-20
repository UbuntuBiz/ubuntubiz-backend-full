# UbuntuBiz Backend

Production-oriented backend operating system for South African informal businesses, particularly spaza shops and small township retailers.

---

## 1. Project Overview & Architecture

UbuntuBiz is designed to manage spaza operations, inventory control, cash flow monitoring, multi-agent AI operations, and collaborative bulk buying integrated with the existing deployed Avalanche Fuji smart contract.

### Technology Stack

- **Framework:** Python 3.12+, FastAPI, Pydantic v2
- **Database & Storage:** PostgreSQL with Row-Level Security (`current_setting('app.business_id')`), SQLite compatibility for local testing, pgvector, SQLAlchemy 2.0, Alembic
- **Blockchain:** Web3.py, Avalanche Fuji C-Chain (Chain ID `43113`), Contract: `0xE019a407a590C4348ea24c92Dc5Ac6C642e22f91`
- **AI Multi-Agent System:** Gemini API, 5 MCP Servers, 7 Specialized Agents
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
  - Automated tests passing (`tests/test_phase1_auth_and_tenant.py`)

- [x] **PHASE 2: Business Operations & Event Ledger**
  - Product catalog management with colloquial township aliases (`bread`, `isinkwa`, etc.)
  - Append-only immutable inventory event ledger (`inventory_events`) with strict idempotency
  - Atomic stock level updates with negative stock protection
  - Compensating reversal event undo workflow (`/api/inventory/undo/{event_id}`)
  - Financial data tracked in integer cents (e.g. 1500 cents = R15.00)
  - Sales service & REST API (`/api/sales`, `/api/sales/summary`)
  - Expense tracking & cash flow reporting (`/api/expenses`)
  - Automated tests passing (`tests/test_phase2_inventory_and_sales.py`)

- [x] **PHASE 3: Blockchain Integration (Avalanche Fuji)**
  - Web3.py provider configured for Avalanche Fuji C-Chain (Chain ID `43113`, RPC: `https://api.avax-test.network/ext/bc/C/rpc`)
  - UbuntuBiz contract wrapper at `0xE019a407a590C4348ea24c92Dc5Ac6C642e22f91`
  - Canonical authentic ABI loader (`app/blockchain/abi/UbuntuBiz.json`) with strict signature validation
  - Non-custodial transaction verification (`/api/blockchain/verify-transaction`) for user-signed Core Wallet transactions
  - Event decoders and synchronization with PostgreSQL (`SaleRecorded`, `PoolCreated`, `PoolJoined`, `OrderCreated`, `OrderApproved`)
  - Idempotency and deduplication on transactions and event identifiers
  - Automated tests passing (`tests/test_phase3_blockchain.py`)

- [x] **PHASE 4: Analytics Automation & Scheduled Jobs**
  - Daily metrics computation: daily sales, gross profit, total expenses, cash variance (`app/services/analytics_service.py`)
  - Automated alert engine: low-stock risk, sales drops (<60% weekday median), alert capping per business
  - Stock health analysis: 30-day velocity, days of stock remaining, dead stock detection
  - Morning business brief generator with factual narrative
  - Background job scripts (`app/jobs/daily_metrics.py`, `app/jobs/alerts.py`, `app/jobs/morning_brief.py`)
  - Analytics REST APIs (`/api/analytics/summary`, `/api/analytics/daily`, `/api/analytics/profit`, `/api/analytics/stock`, `/api/analytics/alerts`, `/api/analytics/morning-brief`)
  - Automated tests passing (`tests/test_phase4_analytics.py`)

- [x] **PHASE 5: Multi-Agent AI Architecture & MCP Servers**
  - 5 Modular MCP Servers implemented: `Inventory MCP`, `Analytics MCP`, `Pool MCP`, `Knowledge MCP`, `Registry MCP`
  - 7 Specialized AI Agents: `Orchestrator`, `Capture`, `Inventory`, `Analytics`, `Procurement`, `Policy & Approval`, `Verification`
  - Human-in-the-loop owner approval flow (`/api/approvals`, `/api/approvals/{id}/decide`) with PIN protection for operations >= R500
  - Strict security guardrails: prompt injection neutralization, tool allowlist enforcement, server-derived tenant context
  - Agent tracing and auditability (`agent_tasks`, `agent_tool_calls`, `/api/ai/tasks/{id}/trace`)
  - Conversational AI endpoint (`/api/ai/chat`)
  - Automated tests passing (`tests/test_phase5_ai_and_mcp.py`)

- [ ] **PHASE 6: RAG Knowledge Base & Procurement Workflows**
- [ ] **PHASE 7: Messaging & Web Chat Simulator**
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
- Gemini API key
- Avalanche Fuji RPC configuration
- Smart contract address
- Redis connection details, if required

Use the values appropriate for your local environment. Never commit your actual `.env` file or expose API keys and private keys in source control.

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
| Phase 1 | Backend Foundation & Architecture | Complete |
| Phase 2 | Business Operations & Event Ledger | Complete |
| Phase 3 | Blockchain Integration | Complete |
| Phase 4 | Analytics Automation & Scheduled Jobs | Complete |
| Phase 5 | Multi-Agent AI Architecture & MCP Servers | Complete |
| Phase 6 | RAG Knowledge Base & Procurement Workflows | Pending |
| Phase 7 | Messaging & Web Chat Simulator | Pending |
| Phase 8 | Testing, Seed Data, Docker & Deployment Readiness | Pending |

---

**UbuntuBiz Backend — Building smarter operations and collaborative purchasing for South African small businesses.**