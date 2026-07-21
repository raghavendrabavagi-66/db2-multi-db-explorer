# DB2 Multi-DB Object Explorer

A small web UI that connects to a list of **DB2 LUW** databases using one shared
username/password, lets you pick an **object type** and a **name filter**, then
traces matching objects across **every** database at once and shows the results
as a table plus a summary. Think of it as running the same catalog lookup you'd
do in DBeaver, but across all your databases in a single click.

## Features

- One shared username/password applied to every database in the list.
- Manage the database list **in-app** via an editable table (add/edit/delete
  rows), with optional persistence to a file.
- First-level filter: object-type buttons (Table, View, MQT, Index, Sequence,
  Alias, Nickname, Trigger, XML Schema, Application Object).
- Second-level filter: `begins with` / `ends with` / `anywhere` / `exact`, plus a
  text box (e.g. `sp_refresh`).
- Queries run in parallel across databases with a progress bar.
- Per-database error capture (an unreachable host never aborts the run).
- Aggregated results table + summary metrics ("X of N databases have MQT
  objects") and a CSV download.
- Read-only: only `SYSCAT` catalog views are queried, never any DDL/DML.
- **DB2 vs Azure Compare** page: row-count comparison per table between one DB2
  schema and one Azure SQL schema, with explicit schema mapping (e.g. USERID → dbo).

## DB2 vs Azure — Table Count Comparison

Open the **DB2 Azure Compare** page from the Streamlit sidebar (multipage app).

1. Enter **DB2** connection (Database, Host, Port, username/password) or paste a JDBC URL.
2. Enter **Azure SQL** server (`*.database.windows.net`), database, and work email (UPN).
3. Map schemas: e.g. DB2 `USERID` → Azure `dbo`.
4. Optional: open **Advanced options** → **Selected tables only** → **Load table list** → pick tables → **Run comparison** (default compares all tables in both schemas).
5. Click **Run comparison** — Azure AD **Interactive MFA** may open a browser sign-in.
6. Review summary KPIs, filter by mismatches, and download CSV.

Tables are matched by **table name** after schema mapping. The app runs your
LISTAGG / STRING_AGG generator queries, executes the resulting UNION count SQL,
and falls back to per-table `COUNT(*)` if the generated SQL is too large.

### Azure SQL prerequisites (Target)

- Install [Microsoft ODBC Driver 18 for SQL Server](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)
- `pip install pyodbc`
- **Authentication** (choose on the compare page):
  - **Azure AD — email + browser sign-in (MFA)** — for `*.database.windows.net` targets
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

1. Enter username + password (sidebar).
2. Click **Edit DB list**, add your databases, and (optionally) **Save to file**.
3. Click an object-type button.
4. Choose a match operator and type the text (e.g. `sp_refresh`).
5. Click **Search across all databases**.

## Project layout

| File                    | Purpose                                                        |
| ----------------------- | ------------------------------------------------------------- |
| `app.py`                | Home: Object Explorer UI                                      |
| `pages/2_DB2_Azure_Compare.py` | DB2 vs Azure table count comparison page               |
| `compare_queries.py`    | LISTAGG / STRING_AGG generator SQL templates                  |
| `compare_engine.py`     | Comparison orchestration, merge, fallback counts              |
| `azure_client.py`       | Azure SQL via pyodbc + Azure AD Interactive MFA               |
| `db2_client.py`         | `ibm_db` connection + parallel per-database execution         |
| `queries.py`            | Object-type -> catalog SQL registry, match-operator patterns  |
| `connections_loader.py` | CSV/list parsing, row-to-connection helpers, save/load         |
| `connections.csv`       | Persisted working list (created by "Save to file")            |
| `sample_connections.csv`| Example connection list (copy to `connections.csv` to seed)   |
| `requirements.txt`      | Python dependencies                                           |

## Security notes

- The password lives only in Streamlit session memory; it is never written to
  disk by this app.
- The name filter is always passed to DB2 as a bound parameter (`?`), so it is
  safe against SQL injection.
