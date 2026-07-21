"""DB2 vs Azure SQL — Table row-count comparison page."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from azure_client import AUTH_METHOD_LABELS, AzureConnection, test_connection as test_azure
from compare_engine import (
    CompareResult,
    comparison_metrics,
    filter_comparison,
    run_comparison,
)
from connections_loader import Connection, parse_jdbc_db2_url
from db2_client import query_single

st.markdown(
    """
    <style>
    .compare-card {
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 1rem 1.25rem;
        margin-bottom: 0.5rem;
        background: #fafafa;
    }
    .compare-card h4 { margin-top: 0; }
    .schema-bridge {
        text-align: center;
        padding: 0.75rem 0;
        color: #555;
        font-size: 0.95rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if "compare_result" not in st.session_state:
    st.session_state.compare_result = None
if "compare_ran_at" not in st.session_state:
    st.session_state.compare_ran_at = None

with st.sidebar:
    st.caption("Connections are configured on this page (not shared with Object Explorer).")

st.title("DB2 vs Azure — Table Count Comparison")
st.caption(
    "Compare exact row counts per table: **Source** (DB2 LUW schema) vs **Target** (Azure SQL schema)."
)
if st.session_state.compare_ran_at:
    st.caption(f"Last run: {st.session_state.compare_ran_at}")

# ---------------------------------------------------------------------------
# Connection cards
# ---------------------------------------------------------------------------
col_db2, col_az = st.columns(2)

with col_db2:
    st.markdown('<div class="compare-card"><h4>Source — DB2 LUW</h4>', unsafe_allow_html=True)
    db2_database = st.text_input("Database", key="cmp_db2_database")
    db2_host = st.text_input("Host", key="cmp_db2_host")
    db2_port = st.number_input("Port", min_value=1, max_value=65535, value=50000, key="cmp_db2_port")
    db2_user = st.text_input("Username", key="cmp_db2_user")
    db2_password = st.text_input("Password", type="password", key="cmp_db2_password")

    with st.expander("Paste JDBC URL"):
        jdbc_in = st.text_input(
            "jdbc:db2://host:port/database",
            key="cmp_db2_jdbc",
            placeholder="jdbc:db2://ss-db22d:50000/infoq",
        )
        if st.button("Apply JDBC", key="cmp_apply_jdbc"):
            parsed = parse_jdbc_db2_url(jdbc_in)
            if parsed:
                dbname, host, port = parsed
                st.session_state.cmp_db2_database = dbname
                st.session_state.cmp_db2_host = host
                st.session_state.cmp_db2_port = port
                st.rerun()
            else:
                st.warning("Could not parse JDBC URL.")

    if st.button("Test DB2 connection", key="cmp_test_db2"):
        if not all([db2_database, db2_host, db2_user, db2_password]):
            st.error("Fill Database, Host, Username, and Password.")
        else:
            conn = Connection(dbname=db2_database, host=db2_host, port=int(db2_port))
            out = query_single(conn, db2_user, db2_password, "SELECT 1 AS OK FROM SYSIBM.SYSDUMMY1")
            if out.ok:
                st.success("DB2 connection OK.")
            else:
                st.error(out.error)
    st.markdown("</div>", unsafe_allow_html=True)

with col_az:
    st.markdown('<div class="compare-card"><h4>Target — Azure SQL</h4>', unsafe_allow_html=True)
    az_server = st.text_input(
        "Server",
        key="cmp_az_server",
        placeholder="gpitd.pres.com\\i2022  or  myserver.database.windows.net",
        help="SSMS-style: host\\instance for named instances. Do not add ,1433 after \\instance.",
    )
    az_database = st.text_input("Database", key="cmp_az_database")
    az_auth = st.radio(
        "Authentication",
        options=list(AUTH_METHOD_LABELS.keys()),
        format_func=lambda k: AUTH_METHOD_LABELS[k],
        key="cmp_az_auth",
        horizontal=False,
    )
    az_trust_cert = st.checkbox(
        "Trust server certificate",
        value=True,
        key="cmp_az_trust_cert",
        help="Match SSMS: Encryption on + trust server certificate.",
    )
    target_table_mode = st.radio(
        "Target table naming",
        options=["original", "staging"],
        format_func=lambda v: (
            "Original — source `table1` ↔ target `table1`"
            if v == "original"
            else "Staging — source `table1` ↔ target `table1_staging`"
        ),
        key="cmp_target_table_mode",
    )
    az_email = ""
    if az_auth == "azure_ad_interactive":
        az_email = st.text_input("Email (UPN)", key="cmp_az_email", placeholder="you@company.com")
        st.caption("A browser window may open for Microsoft sign-in and MFA.")
    else:
        st.caption(
            "Same as SSMS **Windows Authentication** for on-prem instances (e.g. "
            "`gpitd.pres.com\\i2022`). Uses **Trusted_Connection**; run Streamlit on Windows."
        )

    if st.button("Test Target connection", key="cmp_test_az"):
        if not all([az_server, az_database]):
            st.error("Fill Server and Database.")
        elif az_auth == "azure_ad_interactive" and not az_email:
            st.error("Fill Email (UPN) for Azure AD sign-in.")
        else:
            az_conn = AzureConnection(
                server=az_server,
                database=az_database,
                email=az_email,
                auth_method=az_auth,
                trust_server_certificate=az_trust_cert,
            )
            out = test_azure(az_conn)
            if out.ok:
                st.success("Target connection OK.")
            else:
                st.error(out.error)
    st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Schema mapping
# ---------------------------------------------------------------------------
st.markdown("#### Schema mapping")
map_col1, map_mid, map_col2 = st.columns([2, 1, 2])
with map_col1:
    db2_schema = st.text_input("Source schema", value="USERID", key="cmp_db2_schema")
with map_mid:
    st.markdown(
        '<p class="schema-bridge">maps to</p>',
        unsafe_allow_html=True,
    )
with map_col2:
    azure_schema = st.text_input("Target schema", value="dbo", key="cmp_azure_schema")

st.caption(
    f"Schema mapping: **{db2_schema}** → **{azure_schema}**. "
    f"Table pairing: **{target_table_mode}** "
    f"({'`table` ↔ `table`' if target_table_mode == 'original' else '`table` ↔ `table_staging`'})."
)

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
run_col, clear_col, _ = st.columns([1, 1, 3])
with run_col:
    run_clicked = st.button("Run comparison", type="primary", use_container_width=True)
with clear_col:
    if st.button("Clear results", use_container_width=True):
        st.session_state.compare_result = None
        st.session_state.compare_ran_at = None
        st.session_state.cmp_view = "All"
        st.rerun()

if run_clicked:
    errors = []
    if not all([db2_database, db2_host, db2_user, db2_password]):
        errors.append("DB2: Database, Host, Username, and Password are required.")
    if not all([az_server, az_database]):
        errors.append("Target: Server and Database are required.")
    if az_auth == "azure_ad_interactive" and not (az_email or st.session_state.get("cmp_az_email")):
        errors.append("Target: Email (UPN) is required for Azure AD sign-in.")
    if not db2_schema.strip() or not azure_schema.strip():
        errors.append("Both schema names are required.")

    if errors:
        for e in errors:
            st.error(e)
    else:
        progress = st.progress(0.0, text="Starting comparison...")
        status = st.empty()

        def _on_progress(done: int, total: int, msg: str) -> None:
            progress.progress(done / total, text=msg)
            status.caption(msg)

        db2_conn = Connection(
            dbname=db2_database.strip(),
            host=db2_host.strip(),
            port=int(db2_port),
        )
        target_email = (az_email or st.session_state.get("cmp_az_email") or "").strip()
        azure_conn = AzureConnection(
            server=az_server.strip(),
            database=az_database.strip(),
            email=target_email,
            auth_method=az_auth,
            trust_server_certificate=az_trust_cert,
        )

        spinner_msg = (
            "Running comparison..."
            if az_auth == "windows_integrated"
            else "Running comparison (Target sign-in may open in your browser)..."
        )
        with st.spinner(spinner_msg):
            result = run_comparison(
                db2_conn,
                db2_user,
                db2_password,
                db2_schema.strip(),
                azure_conn,
                azure_schema.strip(),
                target_table_mode=target_table_mode,
                on_progress=_on_progress,
            )

        progress.empty()
        status.empty()

        if result.status != "ok":
            st.error(result.error)
            if result.db2.error:
                st.warning(f"DB2 detail: {result.db2.error}")
            if result.azure.error:
                st.warning(f"Azure detail: {result.azure.error}")
        else:
            st.session_state.compare_result = result
            st.session_state.compare_ran_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.session_state.cmp_view = "All"
            fb = []
            if result.db2.used_fallback:
                fb.append("DB2 used per-table fallback")
            if result.azure.used_fallback:
                fb.append("Azure used per-table fallback")
            if fb:
                st.info(" · ".join(fb))
            st.success("Comparison complete.")
            st.rerun()

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
result: CompareResult | None = st.session_state.compare_result
if result is not None and result.status == "ok" and not result.comparison.empty:
    df = result.comparison
    metrics = comparison_metrics(df)

    st.divider()
    st.subheader("Summary")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Tables on Source", metrics["tables_source"])
    m2.metric("Tables on Target", metrics["tables_target"])
    m3.metric("Matched", metrics["matched"])
    m4.metric("Mismatched", metrics["mismatched"])
    m5.metric("Missing on one side", metrics["missing"])

    st.subheader("Comparison")
    view = st.radio(
        "Show",
        ["All", "Matches only", "Mismatches only", "Source only", "Target only"],
        horizontal=True,
        key="cmp_view",
    )
    view_df = filter_comparison(df, view)

    st.dataframe(
        view_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Source Count": st.column_config.NumberColumn(format="%d"),
            "Target Count": st.column_config.NumberColumn(format="%d"),
            "Delta": st.column_config.NumberColumn(format="%+d"),
        },
    )

    st.download_button(
        "Download comparison CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="db2_azure_table_comparison.csv",
        mime="text/csv",
    )

    with st.expander("Generated SQL"):
        st.markdown("**Source (DB2) UNION query**")
        st.code(result.db2.union_sql or "(fallback — no single UNION SQL)", language="sql")
        st.markdown("**Target (Azure) UNION query**")
        st.code(result.azure.union_sql or "(fallback — no single UNION SQL)", language="sql")

elif result is not None and result.status == "ok" and result.comparison.empty:
    st.warning("Comparison ran but no tables were found in either schema.")

else:
    st.info("Configure connections and schema mapping, then click **Run comparison**.")
