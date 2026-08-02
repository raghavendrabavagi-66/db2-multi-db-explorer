import { Link } from "react-router-dom";

const cards = [
  {
    title: "Object Explorer",
    description: "Search procedures, tables, and views across DB2 databases.",
    href: "/legacy/object-explorer",
    disabled: true,
  },
  {
    title: "Row Compare",
    description: "Compare DB2 and Azure SQL table row counts.",
    href: "/row-compare/connections",
    disabled: false,
  },
  {
    title: "Schema Compare",
    description: "GitLab deployment DDL vs live target database.",
    href: "/legacy/schema-compare",
    disabled: true,
  },
];

export function HomePage() {
  return (
    <div className="mx-auto max-w-6xl px-6 py-10">
      <h1 className="text-3xl font-semibold tracking-tight text-on-surface">
        DB2 Migration Studio
      </h1>
      <p className="mt-2 max-w-2xl text-secondary">
        Enterprise workspace for DB2 LUW to Azure SQL migration — row-count validation,
        catalog exploration, and schema compare.
      </p>
      <div className="mt-8 grid gap-4 md:grid-cols-3">
        {cards.map((card) =>
          card.disabled ? (
            <div
              key={card.title}
              className="studio-card flex flex-col justify-between p-6 opacity-60"
            >
              <div>
                <h2 className="text-lg font-semibold">{card.title}</h2>
                <p className="mt-2 text-sm text-secondary">{card.description}</p>
              </div>
              <span className="mt-4 text-xs font-medium uppercase text-secondary">
                Streamlit legacy — migrate next
              </span>
            </div>
          ) : (
            <Link
              key={card.title}
              to={card.href}
              className="studio-card flex flex-col justify-between p-6 transition hover:border-primary"
            >
              <div>
                <h2 className="text-lg font-semibold">{card.title}</h2>
                <p className="mt-2 text-sm text-secondary">{card.description}</p>
              </div>
              <span className="mt-4 text-sm font-semibold text-primary">Enter →</span>
            </Link>
          ),
        )}
      </div>
      <p className="mt-8 text-sm text-secondary">
        React + FastAPI stack on branch <code className="font-mono">react_test</code>.
        Legacy Streamlit UI remains under <code className="font-mono">legacy/streamlit/</code>.
      </p>
    </div>
  );
}
