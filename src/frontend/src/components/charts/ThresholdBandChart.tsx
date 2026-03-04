import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ReferenceLine, ReferenceArea, ResponsiveContainer, Legend,
} from 'recharts';
import { TimeSeriesData } from '@/types/api';
import { RISK_COLORS, THRESHOLD_BAND_COLORS } from '@/design-tokens/colors';
import { formatPeriodLabel, formatValue } from '@/utils/formatters';
import { classifyRisk } from '@/utils/riskClassifier';

interface ThresholdBandChartProps {
  data: TimeSeriesData;
  height?: number;
  showBands?: boolean;
  showComparison?: boolean;
}

const RISK_DOT_COLORS = {
  normal:  '#003366',
  waspada: '#CCCC00',
  siaga:   '#FF69B4',
  krisis:  '#FF0000',
};

function CustomDot(props: Record<string, unknown>) {
  const { cx, cy, payload } = props as { cx: number; cy: number; payload: { riskZone: string } };
  const color = RISK_DOT_COLORS[payload.riskZone as keyof typeof RISK_DOT_COLORS] ?? '#003366';
  return <circle cx={cx} cy={cy} r={4} fill={color} stroke="white" strokeWidth={1.5} />;
}

function CustomTooltip({ active, payload, label, indicator, thresholds }: Record<string, unknown>) {
  if (!active || !(payload as unknown[])?.length) return null;
  const data = (payload as { payload: Record<string, unknown>; dataKey: string; value: number }[])[0];

  return (
    <div className="bg-white border border-gray-200 rounded shadow-lg p-3 text-xs">
      <div className="font-semibold text-gray-700 mb-2">{label as string}</div>
      {(payload as { dataKey: string; value: number; stroke: string }[]).map((p) => (
        <div key={p.dataKey} className="flex justify-between gap-4 mb-1">
          <span style={{ color: p.stroke }}>{p.dataKey === 'simulated' ? 'Simulated' : 'Historical'}</span>
          <span className="tabular-nums font-medium">
            {p.value != null ? formatValue(p.value, indicator as string) : 'N/A'}
          </span>
        </div>
      ))}
      {thresholds && (
        <div className="mt-2 pt-2 border-t border-gray-100 text-gray-500 space-y-0.5">
          <div className="flex justify-between"><span>Waspada:</span><span>{(thresholds as { waspada: number }).waspada}</span></div>
          <div className="flex justify-between"><span>Siaga:</span><span>{(thresholds as { siaga: number }).siaga}</span></div>
          <div className="flex justify-between"><span>Krisis:</span><span>{(thresholds as { krisis: number }).krisis}</span></div>
        </div>
      )}
    </div>
  );
}

export default function ThresholdBandChart({
  data, height = 400, showBands = true, showComparison = true,
}: ThresholdBandChartProps) {
  const { thresholds, direction } = data;

  // Merge simulated + historical into chart data
  const chartData = data.simulated.map((p) => {
    const hist = data.historical.find((h) => h.period === p.period);
    return {
      period: formatPeriodLabel(p.period),
      simulated: p.value,
      historical: hist?.value ?? null,
      riskZone: p.riskZone,
    };
  });

  const allValues = [
    ...data.simulated.map((p) => p.value),
    ...data.historical.map((p) => p.value),
    thresholds.waspada,
    thresholds.siaga,
    thresholds.krisis,
  ].filter((v) => v != null) as number[];

  const yMin = Math.min(...allValues) * 0.9;
  const yMax = Math.max(...allValues) * 1.15;

  // Build threshold bands
  const getBands = () => {
    if (!showBands) return null;
    if (direction === 'inc') {
      return (
        <>
          <ReferenceArea y1={thresholds.waspada} y2={thresholds.siaga} fill={THRESHOLD_BAND_COLORS.waspada} />
          <ReferenceArea y1={thresholds.siaga} y2={thresholds.krisis} fill={THRESHOLD_BAND_COLORS.siaga} />
          <ReferenceArea y1={thresholds.krisis} y2={yMax} fill={THRESHOLD_BAND_COLORS.krisis} />
        </>
      );
    } else {
      return (
        <>
          <ReferenceArea y1={thresholds.siaga} y2={thresholds.waspada} fill={THRESHOLD_BAND_COLORS.waspada} />
          <ReferenceArea y1={thresholds.krisis} y2={thresholds.siaga} fill={THRESHOLD_BAND_COLORS.siaga} />
          <ReferenceArea y1={yMin} y2={thresholds.krisis} fill={THRESHOLD_BAND_COLORS.krisis} />
        </>
      );
    }
  };

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={chartData} margin={{ top: 8, right: 60, bottom: 8, left: 16 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#F0F0F0" />
        {getBands()}
        <ReferenceLine y={thresholds.waspada} stroke="#CCCC00" strokeDasharray="6 3" label={{ value: 'W', position: 'right', fontSize: 10, fill: '#CCCC00' }} />
        <ReferenceLine y={thresholds.siaga} stroke="#FF69B4" strokeDasharray="6 3" label={{ value: 'S', position: 'right', fontSize: 10, fill: '#FF69B4' }} />
        <ReferenceLine y={thresholds.krisis} stroke="#FF0000" strokeDasharray="6 3" label={{ value: 'K', position: 'right', fontSize: 10, fill: '#FF0000' }} />
        <XAxis dataKey="period" tick={{ fontSize: 11 }} />
        <YAxis domain={[yMin, yMax]} tick={{ fontSize: 11 }} />
        <Tooltip content={<CustomTooltip indicator={data.indicator} thresholds={thresholds} />} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        {showComparison && (
          <Line
            type="monotone"
            dataKey="historical"
            name="Historical"
            stroke="#999"
            strokeDasharray="4 4"
            strokeWidth={1.5}
            dot={false}
            connectNulls
          />
        )}
        <Line
          type="monotone"
          dataKey="simulated"
          name="Simulated"
          stroke="#003366"
          strokeWidth={2}
          dot={<CustomDot />}
          connectNulls
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
