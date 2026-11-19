import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { RequireAuth } from "./auth/RequireAuth";
import { Layout } from "./components/Layout";
const StoragePage = lazy(() =>
  import("./pages/StoragePage").then((module) => ({
    default: module.StoragePage,
  })),
);
const EditorPage = lazy(() =>
  import("./pages/EditorPage").then((module) => ({
    default: module.EditorPage,
  })),
);
const CalendarPage = lazy(() =>
  import("./pages/CalendarPage").then((module) => ({
    default: module.CalendarPage,
  })),
);
const GenerationPage = lazy(() =>
  import("./pages/GenerationPage").then((module) => ({
    default: module.GenerationPage,
  })),
);
const SchedulePage = lazy(() =>
  import("./pages/SchedulePage").then((module) => ({
    default: module.SchedulePage,
  })),
);
const ReferenceDataPage = lazy(() =>
  import("./pages/ReferenceDataPage").then((module) => ({
    default: module.ReferenceDataPage,
  })),
);
const LoginPage = lazy(() =>
  import("./pages/LoginPage").then((module) => ({ default: module.LoginPage })),
);
const PublishedSchedulesPage = lazy(() =>
  import("./pages/PublishedSchedulesPage").then((module) => ({
    default: module.PublishedSchedulesPage,
  })),
);
const HistoryPage = lazy(() => import("./pages/HistoryPage"));

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route
            path="/login"
            element={
              <Suspense
                fallback={
                  <p role="status" className="loading-state">
                    Загрузка…
                  </p>
                }
              >
                <LoginPage />
              </Suspense>
            }
          />
          <Route element={<RequireAuth />}>
            <Route path="/" element={<Layout />}>
              <Route index element={<StoragePage />} />
              <Route path="editor" element={<EditorPage />} />
              <Route path="calendar" element={<CalendarPage />} />
              <Route path="generation" element={<GenerationPage />} />
              <Route path="history" element={<HistoryPage />} />
              <Route
                path="published/:publicationId?"
                element={<PublishedSchedulesPage />}
              />
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
