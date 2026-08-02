# DB2 Migration Studio

Enterprise workspace for **DB2 LUW → Azure SQL** migration: catalog exploration,
row-count validation, and GitLab deployment schema compare.

**Stack (branch `react_test`):** React + TypeScript SPA, React Router, Tailwind CSS,
FastAPI REST API, Python domain logic in `db2_explorer/`.

## Quick start

```bash
chmod +x install.sh   # optional — handles Apple Silicon ibm_db
./install.sh          # or: make install

# Terminal 1 — API
PYTHONPATH=. uvicorn backend.app.main:app --reload --port 8000

# Terminal 2 — UI (proxies /api → :8000)
cd frontend && npm install && npm run dev
```

Open [http://localhost:5173](http://localhost:5173):

| Route | Purpose |
| ----- | ------- |
| `/` | Home hub |
| `/row-compare/connections` | DB2 + Azure connection setup |
| `/row-compare/workspace` | Run comparison, metrics, filtered results |

Production: `npm run build` in `frontend/`, then serve `frontend/dist` via FastAPI
(the backend mounts the SPA when `frontend/dist` exists).

## Project layout

```
backend/                 FastAPI app (REST /api/*)
  app/main.py            Entrypoint, CORS, optional SPA static serve
  app/api/routes/        row_compare, object_explorer
frontend/                React + Vite + TypeScript + Tailwind
  src/pages/             Home, Row Compare connections & workspace
  src/lib/               API client, session (rc_sid)
db2_explorer/            Shared Python domain layer (unchanged)
  clients/               DB2 + Azure connectivity
  compare/               Row + schema compare engines
  api/                   Service helpers used by FastAPI routes
legacy/streamlit/        Previous Streamlit UI (Object Explorer, Schema Compare)
stitch_exports/          Design reference HTML from Stitch
design-system/           UI tokens and page specs
Makefile                 dev, build, legacy-streamlit targets
```

## API (Row Compare)

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET | `/api/health` | Health check |
| GET | `/api/rc/connect/{rc_sid}` | Load saved credentials |
| POST | `/api/rc/test-db2` | Test DB2 connection |
| POST | `/api/rc/list-azure-databases` | List Azure SQL databases |
| POST | `/api/rc/save-connect` | Persist credentials server-side |
| POST | `/api/rc/run-comparison` | Execute row-count comparison |

Credentials are stored server-side keyed by `rc_sid` (browser session id); passwords
are never placed in URLs.

## Legacy Streamlit UI

Object Explorer and Schema Compare still run on Streamlit until migrated to React:

```bash
streamlit run legacy/streamlit/app.py
# or: make legacy-streamlit
```

See [legacy/streamlit/requirements.txt](legacy/streamlit/requirements.txt) for Streamlit deps.

## Setup notes

Requires Python 3.9+ and Node 18+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### `ibm_db` on Apple Silicon

If `pip install ibm_db` fails, use `./install.sh` or:

```bash
PY_INCLUDE=$(python3 -c "import sysconfig, os; print(os.path.join(sysconfig.get_path('include')))")
export CFLAGS="-I${PY_INCLUDE}"
pip install ibm_db
```

### Azure SQL prerequisites

- [ODBC Driver 18 for SQL Server](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)
- Entra ID browser sign-in or Windows integrated auth (configured on connections page)

## Security

- GitLab PATs and DB passwords live in session/server memory only.
- Catalog name filters use bound parameters on DB2.
- Entra ID / SSO integration planned for production auth.

## Further reading

Detailed Schema Compare, Object Explorer, and DB2 catalog documentation from the
Streamlit era remains valid for domain behavior — see git history on `ui_test` or
run the legacy Streamlit app for those workflows.
