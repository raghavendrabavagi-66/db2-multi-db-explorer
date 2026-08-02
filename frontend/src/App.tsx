import { Navigate, Route, Routes } from "react-router-dom";
import { StudioLayout } from "./components/layout/StudioLayout";
import { HomePage } from "./pages/HomePage";
import { ConnectionsPage } from "./pages/row-compare/ConnectionsPage";
import { WorkspacePage } from "./pages/row-compare/WorkspacePage";

export default function App() {
  return (
    <Routes>
      <Route element={<StudioLayout />}>
        <Route index element={<HomePage />} />
        <Route path="row-compare">
          <Route index element={<Navigate to="connections" replace />} />
          <Route path="connections" element={<ConnectionsPage />} />
          <Route path="workspace" element={<WorkspacePage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
