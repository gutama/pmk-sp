import { RefreshCw, Settings, HelpCircle } from 'lucide-react';
import { useSimulationStore } from '@/stores/simulationStore';
import ExportButton from '@/components/shared/ExportButton';

export default function Topbar() {
  const { status, activeSimulationId } = useSimulationStore();

  const isRunning = status?.status === 'running';

  return (
    <header className="h-12 bg-white border-b border-gray-200 flex items-center px-4 gap-4 flex-shrink-0">
      <div className="text-sm font-medium text-gray-700">
        FMI-SimEngine
        {activeSimulationId && (
          <span className="ml-2 text-xs text-gray-400 font-mono">
            [{activeSimulationId.slice(0, 8)}...]
          </span>
        )}
      </div>

      {isRunning && (
        <div className="flex items-center gap-2 ml-2">
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          <span className="text-xs text-green-600">
            Running — Day {status?.currentDay}/{status?.totalDays}
          </span>
        </div>
      )}

      <div className="ml-auto flex items-center gap-2">
        <ExportButton />
        <button className="p-2 rounded hover:bg-gray-100 text-gray-500" title="Settings">
          <Settings size={15} />
        </button>
        <button className="p-2 rounded hover:bg-gray-100 text-gray-500" title="Help">
          <HelpCircle size={15} />
        </button>
      </div>
    </header>
  );
}
