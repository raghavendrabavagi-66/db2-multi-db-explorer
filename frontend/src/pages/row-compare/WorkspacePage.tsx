import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { FilterKey, ResultsTable } from "../../components/row-compare/ResultsTable";
import { MetricsGrid } from "../../components/row-compare/MetricsGrid";
import {
  ComparisonMetrics,
  fetchConnect,
  runComparison,
} from "../../lib/rowCompareApi";
import { ConnectCredentials, getRcSessionId, setRcSessionId } from "../../lib/session";

export function WorkspacePage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const urlSid = searchParams.get("rc_sid") || "";

  const [rcSid, setRcSidState] = useState("");
  const [credentials, setCredentials] = useState<ConnectCredentials | null>(null);
  const [tableMode, setTableMode] = useState<"original" | "staging">("original");
  const [filter, setFilter] = useState<FilterKey>("all");
  const [metrics, setMetrics] = useState<ComparisonMetrics | null>(null);
  const [tbodyViews, setTbodyViews] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<{ message: string; error?: boolean } | null>(null);
  const [hasRun, setHasRun] = useState(false);

  const loadCredentials = useCallback(async (sid: string) => {
    const res = await fetchConnect(sid);
    if (!res.ok || !res.credentials) {
      return null;
    }
    return res.credentials;
  }, []);

  useEffect(() => {
    const sid = urlSid || getRcSessionId();
    setRcSidState(sid);
    setRcSessionId(sid);

    void (async () => {
      try {
        const creds = await loadCredentials(sid);
        if (!creds) {
          navigate("/row-compare/connections", { replace: true });
          return;
        }
        setCredentials(creds);
      } catch {
        navigate("/row-compare/connections", { replace: true });
      }
    })();
  }, [urlSid, loadCredentials, navigate]);

  async function handleRunComparison() {
    if (!rcSid) return;
    setBusy(true);
    setToast(null);
    try {
      const res = await runComparison({
        rc_sid: rcSid,
        target_table_mode: tableMode,
      });
      if (res.metrics) {
        setMetrics(res.metrics);
      }
      if (res.tbody_views) {
        setTbodyViews(res.tbody_views);
      } else if (res.tbody_html) {
        setTbodyViews({ all: res.tbody_html });
      }
      setHasRun(true);
      setFilter("all");
      setToast({ message: res.message || "Comparison complete." });
    } catch (err) {
      setToast({
        message: err instanceof Error ? err.message : "Comparison failed.",
        error: true,
      });
    } finally {
      setBusy(false);
    }
  }

  const editHref = `/row-compare/connections?from=workspace&rc_sid=${encodeURIComponent(rcSid)}`;

  return (
    <div className="flex h-[calc(100vh-3rem)] flex-col overflow-hidden">
      <div className="flex h-12 flex-none items-center justify-between border-b border-outline-variant bg-surface-container-lowest px-6">
        <div className="flex items-center gap-3">
          <Link to="/" className="text-sm font-medium text-secondary hover:text-primary">
            ← Home
          </Link>
          <span className="text-outline-variant">|</span>
          <Link to={editHref} className="studio-btn-outline px-3 py-1 text-xs">
            Edit credentials
          </Link>
        </div>
        {credentials && (
          <p className="truncate text-sm text-secondary">
            {credentials.cmp_db2_database} → {credentials.cmp_az_database}
          </p>
        )}
      </div>

      <main className="mx-auto flex min-h-0 w-full max-w-6xl flex-1 flex-col overflow-hidden px-6 py-6">
        <section className="studio-card mb-4 flex-none p-4">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <fieldset>
              <legend className="mb-2 text-xs font-bold uppercase text-secondary">Table type</legend>
              <div className="flex gap-4">
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="radio"
                    name="tableMode"
                    checked={tableMode === "staging"}
                    onChange={() => setTableMode("staging")}
                  />
                  Staging tables
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="radio"
                    name="tableMode"
                    checked={tableMode === "original"}
                    onChange={() => setTableMode("original")}
                  />
                  Main tables
                </label>
              </div>
            </fieldset>
            <button
              type="button"
              className="studio-btn-primary px-6 py-2"
              disabled={busy || !credentials}
              onClick={() => void handleRunComparison()}
            >
              {busy ? "Running…" : "▶ Run comparison"}
            </button>
          </div>
        </section>

        {toast && (
          <div
            className={`mb-4 flex-none rounded px-4 py-2 text-sm ${
              toast.error
                ? "bg-error-container text-on-error-container"
                : "bg-surface-container text-on-surface"
            }`}
          >
            {toast.message}
          </div>
        )}

        {metrics && (
          <div className="mb-4 flex-none">
            <MetricsGrid metrics={metrics} />
          </div>
        )}

        {hasRun && Object.keys(tbodyViews).length > 0 ? (
          <ResultsTable views={tbodyViews} activeFilter={filter} onFilterChange={setFilter} />
        ) : (
          !busy && (
            <div className="studio-card flex flex-1 items-center justify-center p-12 text-secondary">
              Configure connections, then run a comparison to see results.
            </div>
          )
        )}
      </main>
    </div>
  );
}
