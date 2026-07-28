# DB2 Migration Studio

A premium **Streamlit** workspace for DB2 LUW → Azure SQL migration programs: catalog
exploration, row-count validation, and GitLab deployment schema compare with drift sync.

## Features

- **Home hub** — workflow cards for each service with unified navigation.
- **Object Explorer** — search procedures, tables, views, and more across many DB2
  databases in parallel (editable connection list, CSV export).
- **Row Compare** — map DB2 schemas to Azure SQL and compare table row counts.
- **Schema Compare** — GitLab deployment DDL vs live target, side-by-side diff,
  constraint and index sync to staging.
- Shared **design system** (UI UX Pro Max): data-dense dashboard, Fira Sans, enterprise blue palette.
- Read-only catalog queries on DB2; Azure AD browser sign-in for cloud targets.

## Schema Compare — GitLab vs Target Database

Open **Schema Compare** from the Streamlit sidebar.

### GitLab setup

GitLab **URL** (`https://gitlab.com`) and **project ID** (`75690564`) are built into the app. On the Schema Compare page:

1. Enter your **GitLab personal access token** (scopes: **read_api**, **read_repository**).
2. Click **Load branches** and pick a **branch** from the dropdown.

The PAT is kept in your Streamlit session only (same as DB passwords) — no `secrets.toml` file is required for Schema Compare.

### Workflow

1. Enter PAT → **Load branches** → choose branch, **Database folder**, and **Server folder** → **Load deployment**.
2. Enter **Target** server/database (auto-filled from `migration_info.txt` when available) and test the connection.
3. Click **Compare all** — objects are grouped by deployment file (`04_constraints.sql`, `03_table.sql`, …).
4. Expand an object type, select a row, and review the **SQL view** diff (GitLab left, database right; red/green highlights).
5. Use **Show** filters and **Search** to narrow to differences or missing objects.

### Apply constraint drift (GitLab → database)

When GitLab deployment is the source of truth, you can sync **constraints** from `04_constraints.sql` into the target database:

1. Complete **Compare all** (stores the target connection for apply actions).
2. Open **Constraints** — use **Preview batch sync** / **Apply all constraint drifts** for bulk fixes, or select a row and open the **Sync** tab in the DDL pane.
3. Review the generated script:
   - **`only_gitlab`** — `ADD CONSTRAINT` only (object missing in DB).
   - **`different`** — `DROP CONSTRAINT` then `ADD CONSTRAINT` from GitLab (SQL Server cannot alter FK actions or PK columns in place).
4. Check the confirmation box and click **Apply to database**.

### Apply index drift (GitLab → database)

You can sync **indexes** from `05_index.sql` the same way:

1. Complete **Compare all**.
2. Open **Indexes** — use batch sync in the expander, or select a row and open the **Sync** tab.
3. Review the generated script:
   - **`only_gitlab`** and **`different`** — `IF EXISTS DROP INDEX` then `CREATE INDEX` from GitLab (idempotent; fixes ASC/DESC and column-order drift).
4. The **Summary** tab shows index kind and per-column ASC/DESC comparison.
5. Confirm and click **Apply to database**.

**Safety notes (constraints and indexes)**

- Requires `ALTER` permission on the target database.
- Each apply runs in a **transaction** (drop + create rolls back together on failure).
- Batch apply **stops on first failure**; objects applied before the failure remain committed.
- Index recreate on large tables may lock/rebuild — use caution on production.
- Intended for **staging** validation; use caution on production.
- **`only_db`** objects show a suggested DROP script only (not executed from GitLab sync).
- Live index DDL fetch may omit INCLUDE columns or filtered `WHERE` clauses; sync still applies full GitLab CREATE text.

Deployment path pattern:

`db2automation_logs/{database}/{server}/step4_deployment/{bundle}/{01_schema,03_table,04_constraints,...}.sql`

## DB2 vs Azure — Table Count Comparison

Open the **DB2 Azure Compare** page from the Streamlit sidebar (multipage app).

1. Enter **DB2** connection (Database, Host, Port, username/password) or paste a JDBC URL.
2. Enter **Azure SQL** server (`*.database.windows.net`) and database.
3. Map schemas: e.g. DB2 `USERID` → Azure `dbo`.
4. Optional: open **Advanced options** → **Selected tables only** → **Load table list** → pick tables → **Run comparison** (default compares all tables in both schemas).
5. Click **Run comparison** — a browser window opens for Microsoft sign-in (account picker / MFA).
6. Review summary KPIs, filter by mismatches, and download CSV.

Tables are matched by **table name** after schema mapping. The app runs your
LISTAGG / STRING_AGG generator queries, executes the resulting UNION count SQL,
and falls back to per-table `COUNT(*)` if the generated SQL is too large.

### Azure SQL prerequisites (Target)

- Install [Microsoft ODBC Driver 18 for SQL Server](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)
- `pip install pyodbc azure-identity`
- **Authentication** (choose on the compare page):
  - **Azure AD — browser sign-in (account picker / MFA)** — uses `InteractiveBrowserCredential` from `azure-identity`; token is passed to ODBC via `SQL_COPT_SS_ACCESS_TOKEN` (no `UID` in the connection string).
  - **Windows integrated (SSMS-style)** — for on-prem named instances such as
    `gpitd.pres.com\i2022` with **Trust server certificate** (matches SSMS options)
- **Server** field: use SSMS server text exactly (`host\instance`); the app no longer
  appends `,1433` to named instances.

## Object type to DB2 catalog mapping

| Button             | Catalog source                                                        |
| ------------------ | --------------------------------------------------------------------- |
| Table              | `SYSCAT.TABLES` where `TYPE='T'`                                       |
| View               | `SYSCAT.TABLES` where `TYPE='V'`                                       |
| MQT                | `SYSCAT.TABLES` where `TYPE='S'`                                       |
| Alias              | `SYSCAT.TABLES` where `TYPE='A'`                                       |
| Nickname           | `SYSCAT.TABLES` where `TYPE='N'`                                       |
| Index              | `SYSCAT.INDEXES`                                                       |
| Sequence           | `SYSCAT.SEQUENCES`                                                     |
| Trigger            | `SYSCAT.TRIGGERS`                                                      |
| XML Schema         | `SYSCAT.XSROBJECTS`                                                    |
| Application Object | `SYSCAT.ROUTINES` (procedures/functions/UDFs) + `SYSCAT.MODULES` + `SYSCAT.PACKAGES` |

By default, system schemas (`SYS*`) are excluded; toggle "Include system
objects" in the sidebar to include them.

## Managing the database list

The connection list is managed directly in the app:

1. Click **Edit DB list** to open an editable table.
2. For **multiple rows from Excel**, open **Paste from Excel**, copy your rows in
   Excel, paste into the text area (Ctrl+V / Cmd+V), then click **Apply pasted
   rows**. (Pasting several rows directly into the grid puts everything in one
   cell — use the paste area instead.)
3. Or add, edit, or delete single rows in the table (`Database`, `Host`, `Port`).
   Use the toolbar to add (+) or delete rows. `Port` defaults to `50000`.
4. Edits apply immediately for the current session.
5. Click **Save to file** to persist the list to `connections.csv` in the
   project directory. This file is loaded automatically the next time you start
   the app.
6. Click **Reset** to clear the table to empty.

### Seeding from an example

[`sample_connections.csv`](sample_connections.csv) is provided as a reference of
the on-disk format (`dbname,host,port`). To start from it, copy it to
`connections.csv` before launching:

```bash
cp sample_connections.csv connections.csv
```

```csv
dbname,host,port
SAMPLE,db2host1.example.com,50000
TESTDB,db2host2.example.com,50000
PRODDB,db2host3.example.com,60000
```

## Setup

Requires Python 3.9+.

**Recommended (handles macOS Apple Silicon automatically):**

```bash
chmod +x install.sh
./install.sh
```

**Manual install:**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install streamlit pandas
pip install ibm_db          # see note below on Apple Silicon
```

Or install everything at once (works on Linux/Windows; may fail on Apple
Silicon — use `install.sh` instead):

```bash
pip install -r requirements.txt
```

### About the `ibm_db` driver

`ibm_db` is the official IBM driver for DB2 LUW. On most platforms `pip install
ibm_db` also downloads a bundled IBM **clidriver**, so no separate client
install is needed.

- **Linux / Windows / Intel macOS**: usually works out of the box.
- **Apple Silicon (arm64) macOS**: `pip install ibm_db` often fails with
  `No Python.h header file detected` even when Xcode Command Line Tools are
  installed. Fix by pointing the compiler at your Python headers:

  ```bash
  source .venv/bin/activate
  PY_INCLUDE=$(python3 -c "import sysconfig, os; print(os.path.join(sysconfig.get_path('include')))")
  export CFLAGS="-I${PY_INCLUDE}"
  pip install ibm_db
  ```

  Or run `./install.sh`, which does this for you. If `Python.h` is truly
  missing, install Xcode CLT first: `xcode-select --install`.

The app still loads if the driver is missing; it just reports
`ibm_db driver is not installed` per database when you run a search.

## Run

```bash
streamlit run app.py
```

Then in the browser:

1. Open **Home** and pick a workflow, or use the sidebar.
2. **Object Explorer** — username/password in sidebar, edit DB list, search.
3. **Row Compare** / **Schema Compare** — follow on-page connection panels.

## Project layout

```
app.py                          Home hub (navigation + workflow cards)
pages/
  1_Object_Explorer.py          Multi-DB catalog search
  2_Row_Compare.py              DB2 vs Azure row counts
  3_Schema_Compare.py           GitLab DDL vs target + sync
db2_explorer/
  clients/                      DB2 + Azure SQL connectivity
  data/                         Connections, catalog queries, compare SQL
  compare/                      Row + schema compare engines
  ddl/                          Fetch, normalize, diff live DDL
  gitlab/                       GitLab API + deployment parsing
  sync/                         Constraint/index apply to target
  ui/                           Theme tokens + shared Streamlit components
design-system/db2-migration-studio/   Persisted UI UX Pro Max tokens
.streamlit/config.toml          Streamlit theme (primary blue, Fira-friendly)
.cursor/skills/                 Cursor UI/UX Pro Max skills (optional)
```

| Module | Purpose |
| ------ | ------- |
| `db2_explorer/clients/db2.py` | `ibm_db` parallel catalog queries |
| `db2_explorer/clients/azure.py` | pyodbc + InteractiveBrowserCredential |
| `db2_explorer/compare/row_compare.py` | Row-count comparison orchestration |
| `db2_explorer/compare/schema_compare.py` | GitLab vs DB object matching |
| `db2_explorer/gitlab/client.py` | GitLab deployment file fetch |
| `db2_explorer/ui/theme.py` | Global CSS + page bootstrap |
| `connections.csv` | Persisted DB list (Object Explorer) |
| `requirements.txt` | Python dependencies |

## Security notes

- GitLab PATs on Schema Compare are entered in the UI and live in Streamlit session memory only.
- The password lives only in Streamlit session memory; it is never written to
  disk by this app.
- The name filter is always passed to DB2 as a bound parameter (`?`), so it is
  safe against SQL injection.
