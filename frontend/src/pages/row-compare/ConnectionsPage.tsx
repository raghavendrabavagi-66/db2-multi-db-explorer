import { FormEvent, useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  buildSavePayload,
  fetchConnect,
  listAzureDatabases,
  saveConnect,
  testDb2,
} from "../../lib/rowCompareApi";
import { getRcSessionId, setRcSessionId } from "../../lib/session";

export function ConnectionsPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const editMode = searchParams.get("from") === "workspace";
  const urlSid = searchParams.get("rc_sid") || "";

  const [rcSid, setRcSidState] = useState("");
  const [toast, setToast] = useState<{ message: string; error?: boolean } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const [db2Database, setDb2Database] = useState("");
  const [db2Host, setDb2Host] = useState("");
  const [db2Port, setDb2Port] = useState("50000");
  const [db2User, setDb2User] = useState("");
  const [db2Password, setDb2Password] = useState("");

  const [azServer, setAzServer] = useState("");
  const [azDatabase, setAzDatabase] = useState("");
  const [azAuth, setAzAuth] = useState<"entra" | "windows">("entra");
  const [azTrustCert, setAzTrustCert] = useState(false);
  const [azDatabaseOptions, setAzDatabaseOptions] = useState<string[]>([]);

  const showToast = useCallback((message: string, error = false) => {
    setToast({ message, error });
  }, []);

  const loadAzureDbs = useCallback(
    async (server: string, auth: string, trust: boolean) => {
      if (!server.trim()) {
        showToast("Azure SQL Server is required.", true);
        return;
      }
      setBusy("azure-load");
      try {
        const res = await listAzureDatabases({
          server: server.trim(),
          auth_method: auth,
          trust_server_certificate: trust,
        });
        const dbs = res.databases || [];
        setAzDatabaseOptions(dbs);
        if (dbs.length === 1) {
          setAzDatabase(dbs[0]);
        }
        showToast(res.message || `Found ${dbs.length} database(s).`);
      } catch (err) {
        showToast(err instanceof Error ? err.message : "Failed to load databases.", true);
      } finally {
        setBusy(null);
      }
    },
    [showToast],
  );

  useEffect(() => {
    const sid = urlSid || getRcSessionId();
    setRcSidState(sid);
    setRcSessionId(sid);

    void (async () => {
      try {
        const res = await fetchConnect(sid);
        if (!res.ok || !res.credentials) {
          return;
        }
        const c = res.credentials;
        setDb2Database(c.cmp_db2_database);
        setDb2Host(c.cmp_db2_host);
        setDb2Port(String(c.cmp_db2_port));
        setDb2User(c.cmp_db2_user);
        setDb2Password(c.cmp_db2_password);
        setAzServer(c.cmp_az_server);
        setAzDatabase(c.cmp_az_database);
        setAzAuth(c.cmp_az_auth === "windows" ? "windows" : "entra");
        setAzTrustCert(Boolean(c.cmp_az_trust_cert));
        setAzDatabaseOptions((prev) =>
          c.cmp_az_database && !prev.includes(c.cmp_az_database)
            ? [c.cmp_az_database, ...prev]
            : prev,
        );
        if (editMode && c.cmp_az_server) {
          await loadAzureDbs(c.cmp_az_server, c.cmp_az_auth, Boolean(c.cmp_az_trust_cert));
        }
      } catch {
        /* no saved credentials yet */
      }
    })();
  }, [urlSid, editMode, loadAzureDbs]);

  async function handleTestDb2() {
    setBusy("db2-test");
    try {
      const res = await testDb2({
        database: db2Database,
        host: db2Host,
        port: Number(db2Port) || 50000,
        username: db2User,
        password: db2Password,
      });
      showToast(res.message || "DB2 connection OK.");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "DB2 test failed.", true);
    } finally {
      setBusy(null);
    }
  }

  async function handleConnect(e: FormEvent) {
    e.preventDefault();
    const sid = rcSid || getRcSessionId();
    setBusy("save");
    try {
      const res = await saveConnect(
        buildSavePayload(
          sid,
          {
            database: db2Database,
            host: db2Host,
            port: Number(db2Port) || 50000,
            username: db2User,
            password: db2Password,
          },
          {
            server: azServer,
            database: azDatabase,
            auth_method: azAuth,
            trust_server_certificate: azTrustCert,
          },
        ),
      );
      setRcSessionId(sid);
      showToast(res.message || "Connected — ready to run comparison.");
      navigate(`/row-compare/workspace?rc_sid=${encodeURIComponent(sid)}`);
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Failed to save credentials.", true);
    } finally {
      setBusy(null);
    }
  }

  const dbOptions =
    azDatabase && !azDatabaseOptions.includes(azDatabase)
      ? [azDatabase, ...azDatabaseOptions]
      : azDatabaseOptions;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-on-surface/40 p-6 backdrop-blur-sm">
      <form
        onSubmit={handleConnect}
        className="studio-card flex max-h-[95vh] w-full max-w-4xl flex-col overflow-hidden shadow-2xl"
      >
        <div className="flex items-start justify-between border-b border-outline-variant px-8 py-6">
          <div>
            <h1 className="text-2xl font-semibold">
              {editMode ? "Edit Connection" : "Compare Connection Setup"}
            </h1>
            <p className="mt-1 text-sm text-secondary">
              Configure your source and target data environments
            </p>
          </div>
          {editMode ? (
            <Link
              to={`/row-compare/workspace?rc_sid=${encodeURIComponent(rcSid)}`}
              className="rounded px-3 py-2 text-sm text-secondary hover:bg-surface-container"
            >
              ← Back to workspace
            </Link>
          ) : (
            <Link
              to="/"
              className="rounded px-3 py-2 text-sm text-secondary hover:bg-surface-container"
            >
              ✕ Close
            </Link>
          )}
        </div>

        {toast && (
          <div
            className={`mx-8 mt-4 rounded px-4 py-2 text-sm ${
              toast.error
                ? "bg-error-container text-on-error-container"
                : "bg-surface-container text-on-surface"
            }`}
          >
            {toast.message}
          </div>
        )}

        <div className="grid min-h-0 flex-1 divide-x divide-outline-variant overflow-y-auto md:grid-cols-2">
          <section className="p-8">
            <header className="mb-6">
              <h2 className="text-lg font-medium">DB2 LUW Source</h2>
              <p className="text-xs font-bold uppercase tracking-wide text-secondary">
                Local DB2 instance
              </p>
            </header>
            <div className="space-y-4">
              <label className="block">
                <span className="mb-1 block text-xs font-bold uppercase text-secondary">
                  Database name
                </span>
                <input
                  className="studio-input"
                  value={db2Database}
                  onChange={(e) => setDb2Database(e.target.value)}
                  required
                />
              </label>
              <div className="grid grid-cols-3 gap-3">
                <label className="col-span-2 block">
                  <span className="mb-1 block text-xs font-bold uppercase text-secondary">Host</span>
                  <input
                    className="studio-input"
                    value={db2Host}
                    onChange={(e) => setDb2Host(e.target.value)}
                    placeholder="10.0.4.12"
                    required
                  />
                </label>
                <label className="block">
                  <span className="mb-1 block text-xs font-bold uppercase text-secondary">Port</span>
                  <input
                    className="studio-input"
                    value={db2Port}
                    onChange={(e) => setDb2Port(e.target.value)}
                    required
                  />
                </label>
              </div>
              <label className="block">
                <span className="mb-1 block text-xs font-bold uppercase text-secondary">
                  Username
                </span>
                <input
                  className="studio-input"
                  value={db2User}
                  onChange={(e) => setDb2User(e.target.value)}
                  required
                />
              </label>
              <label className="block">
                <span className="mb-1 block text-xs font-bold uppercase text-secondary">
                  Password
                </span>
                <input
                  className="studio-input"
                  type="password"
                  value={db2Password}
                  onChange={(e) => setDb2Password(e.target.value)}
                  required
                />
              </label>
              <button
                type="button"
                className="studio-btn-outline w-full"
                disabled={busy === "db2-test"}
                onClick={() => void handleTestDb2()}
              >
                {busy === "db2-test" ? "Testing…" : "Test connection"}
              </button>
            </div>
          </section>

          <section className="p-8">
            <header className="mb-6">
              <h2 className="text-lg font-medium">Azure SQL Target</h2>
              <p className="text-xs font-bold uppercase tracking-wide text-secondary">
                Production instance
              </p>
            </header>
            <div className="space-y-4">
              <label className="block">
                <span className="mb-1 block text-xs font-bold uppercase text-secondary">
                  Azure SQL server
                </span>
                <input
                  className="studio-input"
                  value={azServer}
                  onChange={(e) => setAzServer(e.target.value)}
                  placeholder="az-db-prod-sql.database.windows.net"
                  required
                />
              </label>
              <fieldset>
                <legend className="mb-2 text-xs font-bold uppercase text-secondary">
                  Authentication
                </legend>
                <div className="space-y-2">
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="radio"
                      name="azAuth"
                      checked={azAuth === "entra"}
                      onChange={() => setAzAuth("entra")}
                    />
                    Microsoft Entra MFA
                  </label>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="radio"
                      name="azAuth"
                      checked={azAuth === "windows"}
                      onChange={() => setAzAuth("windows")}
                    />
                    Windows authentication
                  </label>
                  <label className="ml-6 flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={azTrustCert}
                      onChange={(e) => setAzTrustCert(e.target.checked)}
                    />
                    Trust server certificate
                  </label>
                </div>
              </fieldset>
              <label className="block">
                <span className="mb-1 block text-xs font-bold uppercase text-secondary">
                  Database name
                </span>
                <select
                  className="studio-input"
                  value={azDatabase}
                  onChange={(e) => setAzDatabase(e.target.value)}
                  required
                >
                  <option value="">Select a database…</option>
                  {dbOptions.map((db) => (
                    <option key={db} value={db}>
                      {db}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                className="studio-btn-outline w-full"
                disabled={busy === "azure-load"}
                onClick={() => void loadAzureDbs(azServer, azAuth, azTrustCert)}
              >
                {busy === "azure-load" ? "Loading…" : "Load databases"}
              </button>
            </div>
          </section>
        </div>

        <div className="border-t border-outline-variant p-8">
          <button
            type="submit"
            className="studio-btn-primary h-14 w-full text-base"
            disabled={busy === "save"}
          >
            {busy === "save" ? "Connecting…" : "Connect & compare →"}
          </button>
        </div>
      </form>
    </div>
  );
}
