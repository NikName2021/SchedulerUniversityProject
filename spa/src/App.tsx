import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { RequireAuth } from "./auth/RequireAuth";
import { Layout } from "./components/Layout";
import { StoragePage } from "./pages/StoragePage";
import { EditorPage } from "./pages/EditorPage";
import { CalendarPage } from "./pages/CalendarPage";
import { GenerationPage } from "./pages/GenerationPage";
import HistoryPage from "./pages/HistoryPage";
import { SchedulePage } from "./pages/SchedulePage";
import { ReferenceDataPage } from "./pages/ReferenceDataPage";
import { LoginPage } from "./pages/LoginPage";

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<RequireAuth />}>
            <Route path="/" element={<Layout />}>
              <Route index element={<StoragePage />} />
              <Route path="editor" element={<EditorPage />} />
              <Route path="calendar" element={<CalendarPage />} />
              <Route path="generation" element={<GenerationPage />} />
              <Route path="history" element={<HistoryPage />} />
              <Route path="schedule/:taskId?" element={<SchedulePage />} />
              <Route path="reference" element={<ReferenceDataPage />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
