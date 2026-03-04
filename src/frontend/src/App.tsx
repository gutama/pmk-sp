import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import AppShell from '@/components/layout/AppShell';
import DashboardPage from '@/pages/DashboardPage';
import TimeSeriesPage from '@/pages/TimeSeriesPage';
import NetworkPage from '@/pages/NetworkPage';
import ContagionPage from '@/pages/ContagionPage';
import StressTestPage from '@/pages/StressTestPage';
import ComparisonPage from '@/pages/ComparisonPage';
import ExportPage from '@/pages/ExportPage';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<AppShell />}>
          <Route index element={<DashboardPage />} />
          <Route path="timeseries" element={<TimeSeriesPage />} />
          <Route path="network" element={<NetworkPage />} />
          <Route path="contagion" element={<ContagionPage />} />
          <Route path="stress-test" element={<StressTestPage />} />
          <Route path="comparison" element={<ComparisonPage />} />
          <Route path="export" element={<ExportPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
