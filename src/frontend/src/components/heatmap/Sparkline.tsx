import { useMemo } from 'react';

interface SparklineProps {
  data: (number | null)[];
  width?: number;
  height?: number;
  color?: string;
  thresholdValue?: number;
}

export default function Sparkline({
  data, width = 80, height = 24, color = '#333', thresholdValue,
}: SparklineProps) {
  const points = useMemo(() => {
    const valid = data.filter((d) => d != null) as number[];
    if (valid.length < 2) return null;

    const min = Math.min(...valid);
    const max = Math.max(...valid);
    const range = max - min || 1;
    const xStep = width / (valid.length - 1);
    const pad = height * 0.1;

    return valid.map((v, i) => ({
      x: i * xStep,
      y: height - pad - ((v - min) / range) * (height - 2 * pad),
      value: v,
      breachesThreshold: thresholdValue != null && v > thresholdValue,
    }));
  }, [data, width, height, thresholdValue]);

  if (!points) return <span className="text-gray-400 text-xs">—</span>;

  const pathD = points
    .map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)},${p.y.toFixed(1)}`)
    .join(' ');

  return (
    <svg width={width} height={height} className="inline-block overflow-visible">
      <path d={pathD} fill="none" stroke={color} strokeWidth={1.5} strokeLinejoin="round" />
      {points
        .filter((p) => p.breachesThreshold)
        .map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y} r={2.5} fill="#FF0000" />
        ))}
    </svg>
  );
}
