import { useRef } from 'react';
import { HeatmapData, HeatmapRowData } from '@/types/heatmap';
import HeatmapCell from './HeatmapCell';
import HeatmapSectionHeader from './HeatmapSectionHeader';
import ThresholdColumns from './ThresholdColumns';
import { formatPeriodLabel } from '@/utils/formatters';

interface HeatmapTableProps {
  data: HeatmapData;
  onCellClick?: (indicator: string, period: string) => void;
  comparisonData?: HeatmapData;
}

// NB version row groups
const NB_SECTIONS = [
  {
    id: 'risiko',
    label: 'RISIKO',
    level: 'primary' as const,
    pillars: [
      {
        id: 'risiko_indicators',
        label: null,
        indicators: ['unsettled_banks', 'average_degree', 'system_availability'],
      },
    ],
  },
  {
    id: 'kerentanan',
    label: 'KERENTANAN',
    level: 'primary' as const,
    pillars: [
      {
        id: 'velositas',
        label: '1. Velositas (Risiko Transaksi)',
        indicators: ['tor', 'tor_adj', 'queue_ratio', 'throughput_zona3'],
      },
      {
        id: 'struktur',
        label: '2. Struktur (Risiko Interkoneksi)',
        indicators: ['awd', 'avg_koneksi', 'volatility_interconnectedness'],
      },
      {
        id: 'infrastruktur',
        label: '3. Infrastruktur (Risiko Stabilitas)',
        indicators: ['incidents', 'system_utilization'],
      },
    ],
  },
];

const INDICATOR_LABELS: Record<string, string> = {
  unsettled_banks: 'Unsettled (bank)',
  average_degree: 'AD (Average Degree)',
  system_availability: 'System Availability',
  tor: 'TOR (Turnover Ratio)',
  tor_adj: 'TOR Adj',
  queue_ratio: 'QR (Queue Ratio)',
  throughput_zona3: 'Throughput Zona 3 (%)',
  awd: 'AWD (Avg Weighted Degree)',
  avg_koneksi: 'AVG Koneksi',
  volatility_interconnectedness: 'Volatility Interconnectedness',
  incidents: 'Insiden',
  system_utilization: 'SU (%)',
};

function getRow(data: HeatmapData, indicator: string): HeatmapRowData | undefined {
  return data.rows.find((r) => r.indicator === indicator);
}

export default function HeatmapTable({ data, onCellClick, comparisonData }: HeatmapTableProps) {
  const tableRef = useRef<HTMLDivElement>(null);
  const totalCols = 1 + 3 + data.periods.length; // indicator + W/S/K + periods

  return (
    <div ref={tableRef} className="overflow-auto max-h-[70vh]" id="heatmap-nb-container">
      <table className="border-collapse w-full" style={{ fontFamily: "'IBM Plex Sans', sans-serif" }}>
        <thead className="sticky top-0 z-10">
          <tr>
            <th
              className="text-left px-3 py-2 border-b border-gray-300 bg-[#003366] text-white sticky left-0 z-20"
              style={{ fontSize: '10px', minWidth: 200 }}
            >
              Indikator
            </th>
            <th className="text-center px-2 py-2 border-b border-gray-300 bg-yellow-100 text-yellow-800" style={{ fontSize: '10px', minWidth: 70 }}>
              Waspada
            </th>
            <th className="text-center px-2 py-2 border-b border-gray-300 bg-pink-100 text-pink-800" style={{ fontSize: '10px', minWidth: 70 }}>
              Siaga
            </th>
            <th className="text-center px-2 py-2 border-b border-gray-300 bg-red-100 text-red-800" style={{ fontSize: '10px', minWidth: 70 }}>
              Ditenggarai Krisis
            </th>
            {data.periods.map((p) => (
              <th key={p} className="text-center px-2 py-2 border-b border-gray-300 bg-[#003366] text-white whitespace-nowrap" style={{ fontSize: '10px', minWidth: 65 }}>
                {formatPeriodLabel(p)}
              </th>
            ))}
          </tr>
        </thead>

        <tbody>
          {NB_SECTIONS.map((section) => (
            <>
              <HeatmapSectionHeader
                key={section.id}
                label={section.label}
                colSpan={totalCols}
                level={section.level}
              />
              {section.pillars.map((pillar) => (
                <>
                  {pillar.label && (
                    <HeatmapSectionHeader
                      key={pillar.id}
                      label={pillar.label}
                      colSpan={totalCols}
                      level="secondary"
                    />
                  )}
                  {pillar.indicators.map((indicator) => {
                    const row = getRow(data, indicator);
                    const cmpRow = comparisonData ? getRow(comparisonData, indicator) : undefined;
                    if (!row) return null;

                    return (
                      <tr key={indicator} className="hover:brightness-95 transition-all">
                        <td
                          className="px-3 py-1.5 border-b border-gray-200 bg-white sticky left-0 z-5 whitespace-nowrap"
                          style={{ fontSize: '11px', color: '#1A1A1A', minWidth: 200 }}
                        >
                          {INDICATOR_LABELS[indicator] ?? indicator}
                        </td>
                        <ThresholdColumns
                          waspada={row.thresholds?.waspada ?? null}
                          siaga={row.thresholds?.siaga ?? null}
                          krisis={row.thresholds?.krisis ?? null}
                        />
                        {data.periods.map((period) => {
                          const cell = row.periods[period];
                          if (!cell) return (
                            <td key={period} className="text-center border-b border-gray-200 text-gray-400" style={{ fontSize: '11px', padding: '6px 8px' }}>
                              —
                            </td>
                          );
                          const cmpCell = cmpRow?.periods[period];
                          return (
                            <HeatmapCell
                              key={period}
                              cell={cell}
                              indicator={indicator}
                              period={period}
                              thresholds={row.thresholds}
                              onClick={() => onCellClick?.(indicator, period)}
                              comparisonValue={cmpCell?.value}
                            />
                          );
                        })}
                      </tr>
                    );
                  })}
                </>
              ))}
            </>
          ))}
        </tbody>
      </table>
    </div>
  );
}
