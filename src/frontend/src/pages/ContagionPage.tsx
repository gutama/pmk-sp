import { useState } from 'react';
import { Play, RotateCcw } from 'lucide-react';

export default function ContagionPage() {
  const [lgd, setLgd] = useState(0.6);
  const [maxRounds, setMaxRounds] = useState(10);
  const [failureMode, setFailureMode] = useState('sudden_stop');

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-lg border border-gray-200 px-4 py-3">
        <h2 className="font-bold text-gray-900 text-base">Contagion Simulation</h2>
      </div>

      {/* Shock config */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <h3 className="font-semibold text-gray-700 text-sm mb-3">Shock Configuration</h3>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Failure Mode</label>
            <select
              value={failureMode}
              onChange={(e) => setFailureMode(e.target.value)}
              className="w-full text-xs border border-gray-300 rounded px-2 py-1.5"
            >
              <option value="sudden_stop">Sudden Stop</option>
              <option value="partial">Partial</option>
              <option value="gradual">Gradual</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">LGD: {lgd.toFixed(1)}</label>
            <input type="range" min={0} max={1} step={0.05} value={lgd} onChange={(e) => setLgd(+e.target.value)} className="w-full" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Max Rounds</label>
            <input type="number" value={maxRounds} onChange={(e) => setMaxRounds(+e.target.value)} min={1} max={20} className="w-full text-xs border border-gray-300 rounded px-2 py-1.5" />
          </div>
        </div>
        <div className="flex gap-2 mt-3">
          <button className="flex items-center gap-1.5 px-3 py-1.5 bg-[#003366] text-white rounded text-xs hover:bg-[#004080]">
            <Play size={12} /> Run Contagion
          </button>
          <button className="flex items-center gap-1.5 px-3 py-1.5 border border-gray-300 rounded text-xs hover:bg-gray-50">
            <RotateCcw size={12} /> Reset
          </button>
        </div>
      </div>

      {/* Placeholder for network + cascade log */}
      <div className="grid grid-cols-5 gap-4">
        <div className="col-span-3 bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center justify-center h-80 bg-gray-50 rounded border-2 border-dashed border-gray-200 text-gray-400">
            <div className="text-center">
              <div className="text-3xl mb-2">💥</div>
              <p className="text-sm">Contagion animation renders here</p>
              <p className="text-xs mt-1">Select a bank and run contagion</p>
            </div>
          </div>
        </div>
        <div className="col-span-2 bg-white rounded-lg border border-gray-200 p-4">
          <h3 className="font-semibold text-gray-700 text-sm mb-2">Round Log</h3>
          <div className="text-xs text-gray-500 space-y-2">
            {[1,2,3].map(r => (
              <div key={r} className="border-l-2 border-gray-200 pl-2 py-1">
                <div className="font-medium text-gray-700">Round {r}</div>
                <div className="text-gray-500">Affected: — banks</div>
                <div className="text-gray-500">System loss: —%</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
