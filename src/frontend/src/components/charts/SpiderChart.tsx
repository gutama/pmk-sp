import { useMemo } from 'react';
import { RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer, Legend, Tooltip } from 'recharts';
import { RISK_COLORS } from '@/design-tokens/colors';

interface ScenarioData {
  name: string;
  color: string;
  indicators: Record<string, number>;
}

interface SpiderChartProps {
  scenarios: ScenarioData[];
  axes: string[];
  height?: number;
}

const SCENARIO_COLORS = ['#003366', '#E63946', '#2A9D8F', '#E9C46A'];

export default function SpiderChart({ scenarios, axes, height = 400 }: SpiderChartProps) {
  const chartData = useMemo(() =>
    axes.map((axis) => ({
      subject: axis.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
      ...Object.fromEntries(
        scenarios.map((s, i) => [s.name, s.indicators[axis] ?? 0])
      ),
    })),
    [scenarios, axes]
  );

  return (
    <ResponsiveContainer width="100%" height={height}>
      <RadarChart data={chartData}>
        <PolarGrid />
        <PolarAngleAxis dataKey="subject" tick={{ fontSize: 11 }} />
        <Tooltip />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        {scenarios.map((s, i) => (
          <Radar
            key={s.name}
            name={s.name}
            dataKey={s.name}
            stroke={SCENARIO_COLORS[i % SCENARIO_COLORS.length]}
            fill={SCENARIO_COLORS[i % SCENARIO_COLORS.length]}
            fillOpacity={0.15}
            strokeWidth={2}
          />
        ))}
      </RadarChart>
    </ResponsiveContainer>
  );
}
