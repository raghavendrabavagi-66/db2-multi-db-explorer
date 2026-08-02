type FilterKey = "all" | "mismatch" | "match" | "failed";

interface ResultsTableProps {
  views: Record<string, string>;
  activeFilter: FilterKey;
  onFilterChange: (filter: FilterKey) => void;
}

const filters: { key: FilterKey; label: string }[] = [
  { key: "all", label: "All" },
  { key: "mismatch", label: "Mismatches only" },
  { key: "match", label: "Matches only" },
  { key: "failed", label: "Failed" },
];

export function ResultsTable({ views, activeFilter, onFilterChange }: ResultsTableProps) {
  const html = views[activeFilter] || views.all || "";

  return (
    <section className="studio-card flex min-h-0 flex-1 flex-col overflow-hidden">
      <div className="border-b border-outline-variant bg-surface-container-low px-4 py-3">
        <h2 className="text-lg font-bold">Comparison details</h2>
        <div className="mt-2 flex flex-wrap gap-1">
          {filters.map((f) => (
            <button
              key={f.key}
              type="button"
              onClick={() => onFilterChange(f.key)}
              className={
                activeFilter === f.key
                  ? "border-b-2 border-primary px-3 py-2 text-sm font-bold text-primary"
                  : "px-3 py-2 text-sm font-medium text-secondary hover:bg-surface-container"
              }
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-auto p-0">
        <table className="w-full border-collapse text-left text-sm">
          <thead className="sticky top-0 z-10 bg-surface-container-low">
            <tr className="border-b border-outline-variant">
              <th className="px-4 py-2 text-xs font-bold uppercase text-secondary">Table name</th>
              <th className="px-4 py-2 text-right text-xs font-bold uppercase text-secondary">
                Source count
              </th>
              <th className="px-4 py-2 text-right text-xs font-bold uppercase text-secondary">
                Target count
              </th>
              <th className="px-4 py-2 text-right text-xs font-bold uppercase text-secondary">Delta</th>
              <th className="px-4 py-2 text-xs font-bold uppercase text-secondary">Status</th>
            </tr>
          </thead>
          <tbody dangerouslySetInnerHTML={{ __html: html }} />
        </table>
      </div>
    </section>
  );
}

export type { FilterKey };
