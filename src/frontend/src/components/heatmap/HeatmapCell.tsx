import { HeatmapCellData } from '@/types/heatmap';
import { RISK_COLORS } from '@/design-tokens/colors';
import { useState } from 'react';

interface HeatmapCellProps {
  cell: HeatmapCellData;
  indicator: string;
  period: string;
  thresholds?: { waspada: number; siaga: number; krisis: number } | null;
  onClick?: () => void;
  comparisonValue?: number | null;
}

export default function HeatmapCell({
  cell, indicator, period, thresholds, onClick, comparisonValue,
}: HeatmapCellProps) {
  const [showTooltip, setShowTooltip] = useState(false);
  const colors = RISK_COLORS[cell.riskZone];

  const delta =
    comparisonValue != null && cell.value != null
      ? cell.value - comparisonValue
      : null;

  return (
    <td
      className="relative text-center border-b border-gray-200 cursor-pointer select-none"
      style={{
        backgroundColor: colors.bg,
        color: colors.text,
        fontSize: '11px',
        padding: '6px 8px',
        fontWeight: 500,
        transition: 'opacity 0.15s',
      }}
      onClick={onClick}
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      <span className="tabular-nums">{cell.formattedValue}</span>

      {delta != null && (
        <span className={`ml-1 text-[9px] ${delta > 0 ? 'text-red-700' : 'text-green-700'}`}>
          {delta > 0 ? '▲' : '▼'}{Math.abs(delta).toFixed(2)}
        </span>
      )}

      {showTooltip && (
        <div
          className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 w-52 bg-white border border-gray-200 rounded shadow-lg p-2.5 text-left"
          style={{ fontSize: '11px', color: '#1A1A1A' }}
        >
          <div className="font-semibold text-gray-700 mb-1">{period}</div>
          <div className="flex justify-between mb-0.5">
            <span className="text-gray-500">Value:</span>
            <span className="tabular-nums font-medium">{cell.formattedValue}</span>
          </div>
          <div className="flex justify-between mb-0.5">
            <span className="text-gray-500">Risk Zone:</span>
            <span
              className="px-1.5 rounded font-medium"
              style={{ backgroundColor: colors.bg, color: colors.text, border: `1px solid ${colors.border}` }}
            >
              {cell.riskZone}
            </span>
          </div>
          {thresholds && (
            <div className="mt-1.5 pt-1.5 border-t border-gray-100 text-gray-500 space-y-0.5">
              <div className="flex justify-between">
                <span>Waspada:</span><span className="tabular-nums">{thresholds.waspada}</span>
              </div>
              <div className="flex justify-between">
                <span>Siaga:</span><span className="tabular-nums">{thresholds.siaga}</span>
              </div>
              <div className="flex justify-between">
                <span>Krisis:</span><span className="tabular-nums">{thresholds.krisis}</span>
              </div>
            </div>
          )}
        </div>
      )}
    </td>
  );
}
