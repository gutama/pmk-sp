import { useState } from 'react';
import { Play, Edit2, Plus, CheckCircle, Clock } from 'lucide-react';
import { useMutation } from '@tanstack/react-query';
import { useSimulationStore } from '@/stores/simulationStore';
import SpiderChart from '@/components/charts/SpiderChart';

const SCENARIOS = [
  { name: 'baseline', desc: 'Normal operating conditions', status: 'completed' },
  { name: 'liquidity_squeeze', desc: 'Sudden reduction in interbank liquidity', status: 'ready' },
  { name: 'counterparty_withdrawal', desc: 'Major bank reduces counterparty exposure', status: 'ready' },
  { name: 'infrastructure_disruption', desc: 'Partial system outage', status: 'ready' },
  { name: 'contagion_cascade', desc: 'Bank failure triggers cascading failures', status: 'ready' },
  { name: 'cyber_incident', desc: 'Cyber attack affecting connectivity', status: 'ready' },
];

const SPIDER_AXES = ['tor', 'average_degree', 'awd', 'queue_ratio', 'throughput_zona3', 'system_utilization'];
const MOCK_SPIDER = [
  { name: 'Baseline', color: '#003366', indicators: Object.fromEntries(SPIDER_AXES.map(a => [a, 0.2])) },
  { name: 'Liquidity Squeeze', color: '#E63946', indicators: Object.fromEntries(SPIDER_AXES.map((a, i) => [a, [0.6, 0.3, 0.4, 0.7, 0.65, 0.5][i]])) },
];

export default function StressTestPage() {
  const [selectedScenarios, setSelectedScenarios] = useState<string[]>(['baseline']);
  const { config } = useSimulationStore();

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-lg border border-gray-200 px-4 py-3">
        <h2 className="font-bold text-gray-900 text-base">Scenario Manager</h2>
      </div>

      {/* Scenario grid */}
      <div className="grid grid-cols-3 gap-3">
        {SCENARIOS.map((s) => (
          <div key={s.name} className="bg-white rounded-lg border border-gray-200 p-3 space-y-2">
            <div className="flex items-start justify-between">
              <div>
                <div className="font-semibold text-gray-800 text-sm capitalize">
                  {s.name.replace(/_/g, ' ')}
                </div>
                <p className="text-xs text-gray-500 mt-0.5">{s.desc}</p>
              </div>
              {s.status === 'completed' ? (
                <CheckCircle size={14} className="text-green-500 flex-shrink-0" />
              ) : (
                <Clock size={14} className="text-gray-400 flex-shrink-0" />
              )}
            </div>
            <div className="flex gap-1.5">
              <button className="flex items-center gap-1 px-2.5 py-1 bg-[#003366] text-white rounded text-xs hover:bg-[#004080]">
                <Play size={10} /> Run
              </button>
              <button className="flex items-center gap-1 px-2.5 py-1 border border-gray-300 rounded text-xs hover:bg-gray-50">
                <Edit2 size={10} /> Edit
              </button>
            </div>
          </div>
        ))}

        <div className="bg-white rounded-lg border-2 border-dashed border-gray-200 p-3 flex items-center justify-center text-gray-400 cursor-pointer hover:border-gray-300">
          <div className="text-center">
            <Plus size={20} className="mx-auto mb-1" />
            <span className="text-xs">Custom Scenario</span>
          </div>
        </div>
      </div>

      {/* Spider comparison */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <h3 className="font-semibold text-gray-700 text-sm mb-3">Scenario Comparison (Radar)</h3>
        <SpiderChart scenarios={MOCK_SPIDER} axes={SPIDER_AXES} height={350} />
      </div>
    </div>
  );
}
