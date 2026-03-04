import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import LoadingSpinner from '@/components/shared/LoadingSpinner';
import { useSimulationStore } from '@/stores/simulationStore';

export default function NetworkPage() {
  const { activeSimulationId } = useSimulationStore();
  const [system, setSystem] = useState('rtgs');
  const [colorBy, setColorBy] = useState('tier');

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-lg border border-gray-200 px-4 py-3">
        <h2 className="font-bold text-gray-900 text-base">Network Topology Explorer</h2>

        {/* Controls */}
        <div className="flex flex-wrap gap-4 mt-3">
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500 font-medium">System:</span>
            {['rtgs', 'fast', 'raja', 'combined'].map((s) => (
              <button
                key={s}
                onClick={() => setSystem(s)}
                className={`px-2.5 py-1 rounded text-xs font-medium ${system === s ? 'bg-[#003366] text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
              >
                {s.toUpperCase()}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500 font-medium">Color by:</span>
            {['tier', 'risk', 'centrality', 'debtrank'].map((c) => (
              <button
                key={c}
                onClick={() => setColorBy(c)}
                className={`px-2.5 py-1 rounded text-xs font-medium ${colorBy === c ? 'bg-[#003366] text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
              >
                {c.charAt(0).toUpperCase() + c.slice(1)}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Network Canvas Placeholder */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <div className="flex items-center justify-center h-96 bg-gray-50 rounded border-2 border-dashed border-gray-200 text-gray-400">
          <div className="text-center">
            <div className="text-4xl mb-2">🕸️</div>
            <p className="text-sm font-medium">Network Topology Visualization</p>
            <p className="text-xs mt-1">D3-force directed graph renders here</p>
            <p className="text-xs text-gray-300 mt-1">Run simulation to see live network</p>
          </div>
        </div>
      </div>

      {/* Network summary */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <h3 className="font-semibold text-gray-700 text-sm mb-3">Network Metrics — {system.toUpperCase()}</h3>
        <div className="grid grid-cols-3 gap-4 text-sm">
          {[
            { label: 'Nodes', value: system === 'rtgs' ? 140 : system === 'fast' ? 80 : 70 },
            { label: 'Avg Degree', value: system === 'rtgs' ? '74.07' : system === 'fast' ? '80.00' : '61.00' },
            { label: 'Density', value: '0.530' },
            { label: 'Clustering', value: '0.680' },
            { label: 'Reciprocity', value: '0.820' },
            { label: 'Core Banks', value: system === 'rtgs' ? 18 : system === 'fast' ? 14 : 9 },
          ].map(({ label, value }) => (
            <div key={label} className="text-center border rounded p-3">
              <div className="text-xs text-gray-500">{label}</div>
              <div className="font-bold tabular-nums text-gray-900 mt-1">{value}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
