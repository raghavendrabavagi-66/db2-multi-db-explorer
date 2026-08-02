import { Link, Outlet } from "react-router-dom";

export function StudioLayout() {
  return (
    <div className="flex min-h-full flex-col bg-background">
      <header className="flex h-12 items-center border-b border-outline-variant bg-surface-container-low px-6">
        <Link to="/" className="text-lg font-semibold text-on-surface">
          DB2 Migration Studio
        </Link>
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
    </div>
  );
}
