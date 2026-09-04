# Small Office Management Software

Production-oriented modular monolith foundation for a multi-company, multi-branch office management system.

## Current status

This phase creates architecture and runnable application shells only. Business modules are intentionally not implemented.

## Quick start

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Open <http://localhost:8000/docs>.

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

### Docker Compose

```powershell
Copy-Item .env.example .env
# Set POSTGRES_PASSWORD and SECRET_KEY in .env before starting.
docker compose up --build
```

For an Ubuntu production deployment, secrets, migrations, backups, upgrades,
rollback, and operational checks, see
[docs/deployment-ubuntu.md](docs/deployment-ubuntu.md).

See [docs/architecture.md](docs/architecture.md) for the target architecture and conventions.
