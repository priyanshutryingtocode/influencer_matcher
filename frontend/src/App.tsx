import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { Layout } from "./components/Layout";
import { ComparePage } from "./pages/ComparePage";
import { HistoryPage } from "./pages/HistoryPage";
import { SearchPage } from "./pages/SearchPage";
import "./styles.css";

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Navigate to="/search" replace />} />
          <Route path="search" element={<SearchPage />} />
          <Route path="history" element={<HistoryPage />} />
          <Route path="compare" element={<ComparePage />} />
          <Route path="*" element={<Navigate to="/search" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
