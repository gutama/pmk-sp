import { RiskZone, RISK_COLORS } from '@/design-tokens/colors';

interface RiskBadgeProps {
  zone: RiskZone;
  label?: string;
  size?: 'sm' | 'md';
}

const ZONE_LABELS: Record<RiskZone, string> = {
  normal: 'Normal',
  waspada: 'Waspada',
  siaga: 'Siaga',
  krisis: 'Krisis',
};

export default function RiskBadge({ zone, label, size = 'sm' }: RiskBadgeProps) {
  const colors = RISK_COLORS[zone];
  const text = label ?? ZONE_LABELS[zone];

  return (
    <span
      className={`inline-flex items-center font-medium rounded ${
        size === 'sm' ? 'px-1.5 py-0.5 text-[10px]' : 'px-2.5 py-1 text-xs'
      }`}
      style={{ backgroundColor: colors.bg, color: colors.text, border: `1px solid ${colors.border}` }}
    >
      {text}
    </span>
  );
}
