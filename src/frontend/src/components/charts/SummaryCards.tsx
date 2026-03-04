import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { RiskZone, RISK_COLORS } from '@/design-tokens/colors';
import RiskBadge from '@/components/heatmap/RiskBadge';

interface PillarScore {
  label: string;
  score: number;
  zone: RiskZone;
  trend: 'up' | 'down' | 'flat';
  indicators: number;
  inZone: Record<RiskZone, number>;
}

interface SummaryCardsProps {
  pillars: PillarScore[];
}

export default function SummaryCards({ pillars }: SummaryCardsProps) {
  return (
    <div className="grid grid-cols-4 gap-3">
      {pillars.map((pillar) => {
        const colors = RISK_COLORS[pillar.zone];
        const TrendIcon = pillar.trend === 'up' ? TrendingUp : pillar.trend === 'down' ? TrendingDown : Minus;

        return (
          <div
            key={pillar.label}
            className="bg-white rounded-lg border border-gray-200 p-3 space-y-2"
          >
            <div className="flex items-start justify-between">
              <span className="text-xs font-semibold text-gray-600">{pillar.label}</span>
              <RiskBadge zone={pillar.zone} />
            </div>

            <div className="flex items-end gap-2">
              <span
                className="text-2xl font-bold tabular-nums"
                style={{ color: pillar.zone === 'normal' ? '#003366' : colors.bg }}
              >
                {pillar.score.toFixed(1)}
              </span>
              <TrendIcon
                size={14}
                className={`mb-1.5 ${pillar.trend === 'up' ? 'text-red-500' : pillar.trend === 'down' ? 'text-green-500' : 'text-gray-400'}`}
              />
            </div>

            <div className="flex gap-1.5 text-[10px]">
              {(['normal', 'waspada', 'siaga', 'krisis'] as RiskZone[]).map((z) => {
                const n = pillar.inZone[z];
                if (!n) return null;
                return (
                  <span
                    key={z}
                    className="px-1.5 py-0.5 rounded font-medium"
                    style={{ backgroundColor: RISK_COLORS[z].bg, color: RISK_COLORS[z].text, border: `1px solid ${RISK_COLORS[z].border}` }}
                  >
                    {n}
                  </span>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
