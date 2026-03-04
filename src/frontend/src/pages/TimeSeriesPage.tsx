import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSimulationStore } from '@/stores/simulationStore';
import ThresholdBandChart from '@/components/charts/ThresholdBandChart';
import LoadingSpinner from '@/components/shared/LoadingSpinner';
import { TimeSeriesData } from '@/types/api';
import { formatPeriodLabel } from '@/utils/formatters';

const INDICATORS = [
  { key: 'tor', label: 'TOR' }, { key: 'tor_adj', label: 'TOR Adj' },
  { key: 'queue_ratio', label: 'QR' }, { key: 'throughput_zona3', label: 'Zona3%' },
  { key: 'average_degree', label: 'AD' }, { key: 'awd', label: 'AWD' },
  { key: 'avg_koneksi', label: 'AVG Koneksi' }, { key: 'volatility_interconnectedness', label: 'Vol IC' },
  { key: 'system_utilization', label: 'SU%' }, { key: 'unsettled_banks', label: 'Unsettled' },
];

const PERIODS = ['2025M1','2025M2','2025M3','2025M4','2025M5','2025M6','2025M7','2025M8','2025M9','2025M10','2025M11','2025M12','2026M1'];

const MOCK_DATA: Record<string, number[]> = {
  tor: [1.77,1.69,1.84,2.56,2.70,2.74,1.79,1.43,1.39,1.32,1.21,1.46,1.31],
  tor_adj: [1.19,1.24,1.40,1.78,1.77,1.65,1.37,1.34,1.35,1.20,1.08,1.38,1.13],
  queue_ratio: [4.84,5.24,4.54,4.02,4.05,3.95,4.90,4.76,4.96,5.47,5.93,4.75,4.80],
  throughput_zona3: [25.5,26.5,24.1,27.3,28.6,29.2,29.0,29.5,29.0,27.3,26.8,28.7,26.4],
  average_degree: [74.07,72.45,73.27,70.75,71.45,72.68,75.05,73.49,73.46,73.94,72.89,76.88,74.71],
  awd: [2.32,2.24,2.38,2.31,2.19,2.58,2.84,2.55,2.89,3.24,2.90,3.16,2.85],
  avg_koneksi: [4565,4545,4713,4635,4702,4720,4601,4592,4591,4566,4565,4731,4583],
  volatility_interconnectedness: [234,191,227,168,195,208,121,161,161,130,192,241,155],
  system_utilization: [23.37,22.42,25.18,25.14,25.08,25.70,23.17,24.36,24.39,23.97,24.04,27.00,23.89],
  unsettled_banks: [0,0,1,0,1,0,0,0,0,1,0,0,1],
};

const THRESHOLDS: Record<string, { waspada: number; siaga: number; krisis: number; direction: 'inc' | 'dec' }> = {
  tor: { waspada:1.36, siaga:2.19, krisis:3.03, direction:'inc' },
  tor_adj: { waspada:1.36, siaga:2.19, krisis:3.03, direction:'inc' },
  queue_ratio: { waspada:4.21, siaga:3.98, krisis:2.74, direction:'dec' },
  throughput_zona3: { waspada:40, siaga:50, krisis:60, direction:'inc' },
  average_degree: { waspada:65.80, siaga:63.18, krisis:60.55, direction:'dec' },
  awd: { waspada:2.29, siaga:2.14, krisis:1.98, direction:'dec' },
  avg_koneksi: { waspada:4000, siaga:3959, krisis:3918, direction:'dec' },
  volatility_interconnectedness: { waspada:243, siaga:252, krisis:280, direction:'inc' },
  system_utilization: { waspada:26.94, siaga:27.99, krisis:29.56, direction:'inc' },
  unsettled_banks: { waspada:1, siaga:5, krisis:10, direction:'inc' },
};

function mockTSData(indicator: string): TimeSeriesData {
  const values = MOCK_DATA[indicator] ?? Array(13).fill(1.0);
  const t = THRESHOLDS[indicator] ?? { waspada:1, siaga:5, krisis:10, direction:'inc' as const };

  function zone(v: number): string {
    if (t.direction === 'inc') {
      if (v < t.waspada) return 'normal';
      if (v < t.siaga) return 'waspada';
      if (v < t.krisis) return 'siaga';
      return 'krisis';
    } else {
      if (v > t.waspada) return 'normal';
      if (v > t.siaga) return 'waspada';
      if (v > t.krisis) return 'siaga';
      return 'krisis';
    }
  }

  const pts = PERIODS.map((p, i) => ({ period: p, value: values[i] ?? null, riskZone: values[i] != null ? zone(values[i]) : 'normal' }));
  const vals = values.filter(v => v != null);
  return {
    simulationId: 'demo',
    indicator,
    simulated: pts,
    historical: pts,
    thresholds: { waspada: t.waspada, siaga: t.siaga, krisis: t.krisis },
    direction: t.direction,
    statistics: {
      mean: vals.reduce((a,b)=>a+b,0)/vals.length,
      std: Math.sqrt(vals.map(v => Math.pow(v - vals.reduce((a,b)=>a+b,0)/vals.length, 2)).reduce((a,b)=>a+b,0)/vals.length),
      min: Math.min(...vals),
      max: Math.max(...vals),
    },
  };
}

export default function TimeSeriesPage() {
  const [selected, setSelected] = useState('tor');
  const { activeSimulationId, status } = useSimulationStore();

  const { data: tsData, isLoading } = useQuery({
    queryKey: ['timeseries', activeSimulationId, selected],
    queryFn: async () => {
      if (!activeSimulationId || status?.status !== 'completed') return mockTSData(selected);
      const res = await fetch(`/api/results/${activeSimulationId}/timeseries?indicator=${selected}`);
      if (!res.ok) return mockTSData(selected);
      return res.json() as Promise<TimeSeriesData>;
    },
    enabled: true,
    initialData: () => mockTSData(selected),
  });

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-lg border border-gray-200 px-4 py-3">
        <h2 className="font-bold text-gray-900 text-base mb-3">Time-Series Deep Dive</h2>

        {/* Indicator pills */}
        <div className="flex flex-wrap gap-2">
          {INDICATORS.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setSelected(key)}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                selected === key
                  ? 'bg-[#003366] text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Main chart */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <h3 className="font-semibold text-gray-700 text-sm mb-3">
          {INDICATORS.find(i => i.key === selected)?.label ?? selected}
        </h3>
        {isLoading ? <LoadingSpinner /> : tsData && <ThresholdBandChart data={tsData} height={400} />}
      </div>

      {/* Statistics */}
      {tsData && (
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <h3 className="font-semibold text-gray-700 text-sm mb-3">Statistics</h3>
          <div className="grid grid-cols-4 gap-4">
            {Object.entries(tsData.statistics).map(([k, v]) => (
              <div key={k} className="text-center">
                <div className="text-xs text-gray-500 capitalize">{k}</div>
                <div className="font-bold tabular-nums text-gray-900">{(v as number).toFixed(3)}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
