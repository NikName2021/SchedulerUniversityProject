import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from './components/Layout';
import { DashboardPage } from './pages/DashboardPage';
import { ImportPage } from './pages/ImportPage';
import { TeachersPage } from './pages/TeachersPage';
import { SchedulePage } from './pages/SchedulePage';
import { useAppStore } from './store/useAppStore';

function App() {
  const fetchInitialData = useAppStore((state) => state.fetchInitialData);

  React.useEffect(() => {
    fetchInitialData();
  }, [fetchInitialData]);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<DashboardPage />} />
          <Route path="import" element={<ImportPage />} />
          <Route path="teachers" element={<TeachersPage />} />
          <Route path="schedule" element={<SchedulePage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
