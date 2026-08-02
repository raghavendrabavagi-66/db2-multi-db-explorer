import { ComparisonMetrics } from "../../lib/rowCompareApi";

interface MetricsGridProps {
  metrics: ComparisonMetrics;
}

export function MetricsGrid({ metrics }: MetricsGridProps) {
  const items = [
    { label: "Total tables", value: metrics.tables_source, accent: "" },
    { label: "Matches", value: metrics.matched, accent: "border-l-emerald-500 text-emerald-700" },
    { label: "Mismatches", value: metrics.mismatched, accent: "border-l-amber-500 text-amber-700" },
    { label: "Failed", value: metrics.missing, accent: "border-l-red-500 text-red-700" },
    { label: "Rows scanned", value: metrics.rows_label, accent: "" },
  ];

  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-5">
      {items.map((item) => (
        <div
          key={item.label}
          className={`studio-card border-l-4 px-4 py-5 ${item.accent || "border-l-transparent"}`}
        >
          <p className="text-xs font-bold uppercase tracking-wide text-secondary">{item.label}</p>
          <p className="mt-1 text-2xl font-bold">{item.value}</p>
        </div>
      ))}
    </div>
  );
}
