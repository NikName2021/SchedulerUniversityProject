import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from './components/Layout';
import { StoragePage } from './pages/StoragePage';
import { EditorPage } from './pages/EditorPage';
import { CalendarPage } from './pages/CalendarPage';
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
          <Route index element={<StoragePage />} />
          <Route path="editor" element={<EditorPage />} />
          <Route path="calendar" element={<CalendarPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
