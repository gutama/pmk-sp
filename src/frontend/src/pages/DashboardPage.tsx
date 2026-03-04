import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSimulationStore } from '@/stores/simulationStore';
import { useUIStore } from '@/stores/uiStore';
import { HeatmapData } from '@/types/heatmap';
import HeatmapTable from '@/components/heatmap/HeatmapTable';
import LoadingSpinner from '@/components/shared/LoadingSpinner';
import RiskBadge from '@/components/heatmap/RiskBadge';
import SummaryCards from '@/components/charts/SummaryCards';
import { RiskZone } from '@/design-tokens/colors';

function mockHeatmapData(version: 'nb' | 'pmkt'): HeatmapData {
  const periods = [
    '2025M1','2025M2','2025M3','2025M4','2025M5','2025M6',
    '2025M7','2025M8','2025M9','2025M10','2025M11','2025M12','2026M1',
  ];
  const historicalTOR = [1.77, 1.69, 1.84, 2.56, 2.70, 2.74, 1.79, 1.43, 1.39, 1.32, 1.21, 1.46, 1.31];
  const historicalAD = [74.07, 72.45, 73.27, 70.75, 71.45, 72.68, 75.05, 73.49, 73.46, 73.94, 72.89, 76.88, 74.71];
  const historicalSU = [23.37, 22.42, 25.18, 25.14, 25.08, 25.70, 23.17, 24.36, 24.39, 23.97, 24.04, 27.00, 23.89];

  const makeRow = (indicator: string, values: (number | null)[], thresholds: { waspada: number; siaga: number; krisis: number; direction: 'inc' | 'dec' }, fmt: (v: number) => string) => ({
    indicator,
    label: indicator,
    pillar: 'risiko' as const,
    thresholds,
    periods: Object.fromEntries(periods.map((p, i) => {
      const val = values[i] ?? null;
      const zone = val == null ? 'normal' : classifyRiskLocal(val, thresholds);
      return [p, { value: val, riskZone: zone as RiskZone, formattedValue: val == null ? 'TBU' : fmt(val) }];
    })),
  });

  function classifyRiskLocal(v: number, t: { waspada: number; siaga: number; krisis: number; direction: 'inc' | 'dec' }): string {
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

  const rows = [
    makeRow('unsettled_banks', [0,0,1,0,1,0,0,0,0,1,0,0,1], { waspada:1, siaga:5, krisis:10, direction:'inc' }, (v) => v.toFixed(0)),
    makeRow('average_degree', historicalAD, { waspada:65.80, siaga:63.18, krisis:60.55, direction:'dec' }, (v) => v.toFixed(2)),
    makeRow('system_availability', [100,100,100,100,100,100,100,100,100,100,100,100,100], { waspada:97, siaga:98.5, krisis:99.975, direction:'dec' }, (v) => `${v.toFixed(3)}%`),
    makeRow('tor', historicalTOR, { waspada:1.36, siaga:2.19, krisis:3.03, direction:'inc' }, (v) => v.toFixed(2)),
    makeRow('tor_adj', [1.19,1.24,1.40,1.78,1.77,1.65,1.37,1.34,1.35,1.20,1.08,1.38,1.13], { waspada:1.36, siaga:2.19, krisis:3.03, direction:'inc' }, (v) => v.toFixed(2)),
    makeRow('queue_ratio', [4.84,5.24,4.54,4.02,4.05,3.95,4.90,4.76,4.96,5.47,5.93,4.75,null], { waspada:4.21, siaga:3.98, krisis:2.74, direction:'dec' }, (v) => v.toFixed(2)),
    makeRow('throughput_zona3', [25.5,26.5,24.1,27.3,28.6,29.2,29.0,29.5,29.0,27.3,26.8,28.7,26.4], { waspada:40, siaga:50, krisis:60, direction:'inc' }, (v) => `${v.toFixed(1)}%`),
    makeRow('awd', [2.32,2.24,2.38,2.31,2.19,2.58,2.84,2.55,2.89,3.24,2.90,3.16,2.85], { waspada:2.29, siaga:2.14, krisis:1.98, direction:'dec' }, (v) => v.toFixed(2)),
    makeRow('avg_koneksi', [4565,4545,4713,4635,4702,4720,4601,4592,4591,4566,4565,4731,4583], { waspada:4000, siaga:3959, krisis:3918, direction:'dec' }, (v) => v.toLocaleString('id-ID', {maximumFractionDigits:0})),
    makeRow('volatility_interconnectedness', [234,191,227,168,195,208,121,161,161,130,192,241,155], { waspada:243, siaga:252, krisis:280, direction:'inc' }, (v) => v.toFixed(0)),
    makeRow('system_utilization', historicalSU, { waspada:26.94, siaga:27.99, krisis:29.56, direction:'inc' }, (v) => `${v.toFixed(2)}%`),
  ];

  return {
    version,
    simulationId: 'demo',
    periods,
    rows,
    overallRiskZone: 'normal',
    generatedAt: new Date().toISOString(),
  };
}

export default function DashboardPage() {
  const { activeSimulationId, status } = useSimulationStore();
  const { selectedTab, setTab } = useUIStore();
  const [selectedCell, setSelectedCell] = useState<{ indicator: string; period: string } | null>(null);

  const { data: heatmap, isLoading } = useQuery({
    queryKey: ['heatmap', activeSimulationId, selectedTab],
    queryFn: async () => {
      if (!activeSimulationId || status?.status !== 'completed') {
        return mockHeatmapData(selectedTab);
      }
      const res = await fetch(`/api/results/${activeSimulationId}/heatmap?version=${selectedTab}`);
      if (!res.ok) return mockHeatmapData(selectedTab);
      return res.json() as Promise<HeatmapData>;
    },
    enabled: true,
    initialData: () => mockHeatmapData(selectedTab),
  });

  const summaryPillars = [
    { label: 'Velositas', score: 1.8, zone: 'normal' as RiskZone, trend: 'flat' as const, indicators: 4, inZone: { normal: 4, waspada: 0, siaga: 0, krisis: 0 } },
    { label: 'Struktur', score: 2.1, zone: 'normal' as RiskZone, trend: 'down' as const, indicators: 3, inZone: { normal: 3, waspada: 0, siaga: 0, krisis: 0 } },
    { label: 'Infrastruktur', score: 1.2, zone: 'normal' as RiskZone, trend: 'flat' as const, indicators: 2, inZone: { normal: 2, waspada: 0, siaga: 0, krisis: 0 } },
    { label: 'Agregat', score: 1.7, zone: 'normal' as RiskZone, trend: 'flat' as const, indicators: 9, inZone: { normal: 9, waspada: 0, siaga: 0, krisis: 0 } },
  ];

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="bg-white rounded-lg border border-gray-200 px-4 py-3 flex items-center justify-between">
        <div>
          <h1 className="font-bold text-gray-900 text-base">Heatmap Subprotokol SP</h1>
          <p className="text-xs text-gray-500 mt-0.5">
            Risiko SP relatif stabil — {activeSimulationId ? `Sim: ${activeSimulationId.slice(0,8)}...` : 'Data Demo (Jan-25 s.d. Jan-26)'}
          </p>
        </div>
        <RiskBadge zone={heatmap?.overallRiskZone ?? 'normal'} size="md" label={`Overall: ${(heatmap?.overallRiskZone ?? 'Normal').toUpperCase()}`} />
      </div>

      {/* Summary cards */}
      <SummaryCards pillars={summaryPillars} />

      {/* Heatmap */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        {/* Tab bar */}
        <div className="flex border-b border-gray-200">
          {(['nb', 'pmkt'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setTab(tab)}
              className={`px-4 py-2.5 text-xs font-medium transition-colors ${
                selectedTab === tab
                  ? 'border-b-2 border-[#003366] text-[#003366]'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {tab === 'nb' ? 'Versi NB (Neraca Bank)' : 'Versi PMKT (Makroprudensial)'}
            </button>
          ))}
        </div>

        {isLoading ? (
          <LoadingSpinner />
        ) : (
          <HeatmapTable
            data={heatmap!}
            onCellClick={(indicator, period) => setSelectedCell({ indicator, period })}
          />
        )}

        {/* Legend */}
        <div className="flex items-center gap-4 px-4 py-2 bg-gray-50 border-t border-gray-200">
          <span className="text-xs text-gray-500 font-medium">Threshold Legend:</span>
          {(['normal', 'waspada', 'siaga', 'krisis'] as RiskZone[]).map((zone) => (
            <span key={zone} className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-sm inline-block" style={{ backgroundColor: zone === 'normal' ? '#E5E7EB' : RISK_COLORS_SIMPLE[zone] }} />
              <span className="text-xs text-gray-600 capitalize">{zone}</span>
            </span>
          ))}
        </div>
      </div>

      {/* Selected cell detail */}
      {selectedCell && (
        <div className="bg-white rounded-lg border border-gray-200 p-3 text-xs">
          <p className="font-medium">Selected: {selectedCell.indicator} — {selectedCell.period}</p>
          <button onClick={() => setSelectedCell(null)} className="text-gray-400 hover:text-gray-600 mt-1">
            Clear selection
          </button>
        </div>
      )}
    </div>
  );
}

const RISK_COLORS_SIMPLE: Record<string, string> = {
  waspada: '#FFFF00',
  siaga: '#FF69B4',
  krisis: '#FF0000',
};
