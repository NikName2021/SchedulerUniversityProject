import React from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Layout } from "./components/Layout";
import { StoragePage } from "./pages/StoragePage";
import { EditorPage } from "./pages/EditorPage";
import { CalendarPage } from "./pages/CalendarPage";
import { GenerationPage } from "./pages/GenerationPage";
import HistoryPage from "./pages/HistoryPage";
import { SchedulePage } from "./pages/SchedulePage";
import { ReferenceDataPage } from "./pages/ReferenceDataPage";
import { useAppStore } from "./store/useAppStore";

function App() {
  const fetchInitialData = useAppStore((state) => state.fetchInitialData);

  React.useEffect(() => {
    fetchInitialData();
  }, [fetchInitialData]);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<StoragePage />} />
          <Route path="editor" element={<EditorPage />} />
          <Route path="calendar" element={<CalendarPage />} />
          <Route path="generation" element={<GenerationPage />} />
          <Route path="history" element={<HistoryPage />} />
          <Route path="schedule/:taskId?" element={<SchedulePage />} />
          <Route path="reference" element={<ReferenceDataPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
