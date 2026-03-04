import { ThresholdConfig } from '@/types/heatmap';
import { RiskZone } from '@/design-tokens/colors';

export function classifyRisk(
  value: number | null,
  threshold: ThresholdConfig | null
): RiskZone {
  if (value === null || threshold === null) return 'normal';

  if (threshold.direction === 'inc') {
    if (value < threshold.waspada) return 'normal';
    if (value < threshold.siaga)   return 'waspada';
    if (value < threshold.krisis)  return 'siaga';
    return 'krisis';
  } else {
    if (value > threshold.waspada) return 'normal';
    if (value > threshold.siaga)   return 'waspada';
    if (value > threshold.krisis)  return 'siaga';
    return 'krisis';
  }
}

export function normalizeForSpider(
  value: number,
  threshold: ThresholdConfig
): number {
  const { waspada, siaga, krisis, direction } = threshold;

  if (direction === 'inc') {
    if (value <= waspada) return (value / waspada) * 0.33;
    if (value <= siaga)   return 0.33 + ((value - waspada) / (siaga - waspada)) * 0.33;
    if (value <= krisis)  return 0.66 + ((value - siaga) / (krisis - siaga)) * 0.34;
    return 1.0;
  } else {
    if (value >= waspada) return (1 - (waspada / value)) * 0.33;
    if (value >= siaga)   return 0.33 + ((waspada - value) / (waspada - siaga)) * 0.33;
    if (value >= krisis)  return 0.66 + ((siaga - value) / (siaga - krisis)) * 0.34;
    return 1.0;
  }
}

export function getOverallRiskZone(zones: RiskZone[]): RiskZone {
  const order: Record<RiskZone, number> = { normal: 0, waspada: 1, siaga: 2, krisis: 3 };
  return zones.reduce<RiskZone>((max, z) => order[z] > order[max] ? z : max, 'normal');
}
