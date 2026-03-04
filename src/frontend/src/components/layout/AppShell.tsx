import { Outlet, NavLink } from 'react-router-dom';
import { BarChart2, GitMerge, Activity, Zap, Settings2, GitCompare, Download, ChevronLeft, ChevronRight } from 'lucide-react';
import { useUIStore } from '@/stores/uiStore';
import Sidebar from './Sidebar';
import Topbar from './Topbar';

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Heatmap', icon: BarChart2, end: true },
  { to: '/dashboard/timeseries', label: 'Time-Series', icon: Activity },
  { to: '/dashboard/network', label: 'Network', icon: GitMerge },
  { to: '/dashboard/contagion', label: 'Contagion', icon: Zap },
  { to: '/dashboard/stress-test', label: 'Stress Test', icon: Settings2 },
  { to: '/dashboard/comparison', label: 'Comparison', icon: GitCompare },
  { to: '/dashboard/export', label: 'Export', icon: Download },
];

export default function AppShell() {
  const { sidebarOpen, toggleSidebar } = useUIStore();

  return (
    <div className="flex h-screen bg-gray-100 overflow-hidden">
      {/* Sidebar */}
      <aside
        className={`flex flex-col transition-all duration-200 bg-white border-r border-gray-200 ${
          sidebarOpen ? 'w-64' : 'w-14'
        }`}
      >
        {/* Logo */}
        <div className="flex items-center px-3 py-4 border-b border-gray-200 bg-[#003366] text-white">
          {sidebarOpen && (
            <span className="font-bold text-sm truncate">FMI-SimEngine</span>
          )}
          <button
            onClick={toggleSidebar}
            className="ml-auto p-1 rounded hover:bg-[#004080] transition-colors"
          >
            {sidebarOpen ? <ChevronLeft size={16} /> : <ChevronRight size={16} />}
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-3 overflow-y-auto">
          {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 mx-2 my-0.5 rounded-lg text-sm transition-colors ${
                  isActive
                    ? 'bg-[#003366] text-white'
                    : 'text-gray-600 hover:bg-gray-100'
                }`
              }
            >
              <Icon size={16} className="flex-shrink-0" />
              {sidebarOpen && <span className="truncate">{label}</span>}
            </NavLink>
          ))}
        </nav>

        {/* Simulation control panel */}
        {sidebarOpen && <Sidebar />}
      </aside>

      {/* Main content */}
      <div className="flex flex-col flex-1 overflow-hidden">
        <Topbar />
        <main className="flex-1 overflow-auto p-4">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
