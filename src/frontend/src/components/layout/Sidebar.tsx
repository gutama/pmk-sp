import { Play, Pause, RotateCcw } from 'lucide-react';
import { useSimulationStore } from '@/stores/simulationStore';
import { useMutation } from '@tanstack/react-query';

async function startSimulation(config: Record<string, unknown>) {
  const res = await fetch('/api/simulate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });
  if (!res.ok) throw new Error('Simulation failed to start');
  return res.json();
}

const SCENARIOS = [
  'baseline', 'liquidity_squeeze', 'counterparty_withdrawal',
  'infrastructure_disruption', 'contagion_cascade', 'cyber_incident',
];

export default function Sidebar() {
  const { config, setConfig, status, setStatus, setActiveSimulation } = useSimulationStore();
  const isRunning = status?.status === 'running';

  const runMutation = useMutation({
    mutationFn: startSimulation,
    onSuccess: (data) => {
      setActiveSimulation(data.simulation_id);
      setStatus({ simulationId: data.simulation_id, status: 'pending', progressPct: 0, currentDay: 0, totalDays: config.nDays });
    },
  });

  const handleRun = () => {
    runMutation.mutate({
      n_banks: config.nBanks,
      n_days: config.nDays,
      scenario: config.scenario,
      seed: config.seed,
      systems: config.systems,
      tick_interval_min: config.tickIntervalMin,
    });
  };

  const progressPct = status?.progressPct ?? 0;

  return (
    <div className="border-t border-gray-200 p-3 space-y-3 text-xs">
      {/* Scenario selector */}
      <div>
        <label className="block text-gray-500 mb-1 font-medium">Scenario</label>
        <select
          value={config.scenario}
          onChange={(e) => setConfig({ scenario: e.target.value })}
          className="w-full text-xs border border-gray-300 rounded px-2 py-1"
        >
          {SCENARIOS.map((s) => (
            <option key={s} value={s}>
              {s.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
            </option>
          ))}
        </select>
      </div>

      {/* Parameters */}
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="block text-gray-500 mb-1">Banks</label>
          <input
            type="number"
            value={config.nBanks}
            onChange={(e) => setConfig({ nBanks: +e.target.value })}
            className="w-full text-xs border border-gray-300 rounded px-2 py-1"
            min={10} max={500}
          />
        </div>
        <div>
          <label className="block text-gray-500 mb-1">Days</label>
          <input
            type="number"
            value={config.nDays}
            onChange={(e) => setConfig({ nDays: +e.target.value })}
            className="w-full text-xs border border-gray-300 rounded px-2 py-1"
            min={1} max={365}
          />
        </div>
        <div>
          <label className="block text-gray-500 mb-1">Seed</label>
          <input
            type="number"
            value={config.seed}
            onChange={(e) => setConfig({ seed: +e.target.value })}
            className="w-full text-xs border border-gray-300 rounded px-2 py-1"
          />
        </div>
        <div>
          <label className="block text-gray-500 mb-1">Tick (min)</label>
          <input
            type="number"
            value={config.tickIntervalMin}
            onChange={(e) => setConfig({ tickIntervalMin: +e.target.value })}
            className="w-full text-xs border border-gray-300 rounded px-2 py-1"
            min={1} max={60}
          />
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-2">
        <button
          onClick={handleRun}
          disabled={isRunning}
          className="flex items-center gap-1 px-3 py-1.5 bg-[#003366] text-white rounded text-xs hover:bg-[#004080] disabled:opacity-50"
        >
          <Play size={12} />
          Run
        </button>
        <button
          disabled={!isRunning}
          className="flex items-center gap-1 px-3 py-1.5 border border-gray-300 rounded text-xs hover:bg-gray-50 disabled:opacity-50"
        >
          <Pause size={12} />
          Pause
        </button>
        <button
          className="flex items-center gap-1 px-3 py-1.5 border border-gray-300 rounded text-xs hover:bg-gray-50"
        >
          <RotateCcw size={12} />
        </button>
      </div>

      {/* Progress */}
      {status && (
        <div>
          <div className="flex justify-between text-gray-500 mb-1">
            <span>Day {status.currentDay}/{status.totalDays}</span>
            <span>{progressPct.toFixed(0)}%</span>
          </div>
          <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-[#003366] transition-all duration-300"
              style={{ width: `${progressPct}%` }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
