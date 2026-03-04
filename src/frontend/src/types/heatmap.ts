import { RiskZone } from '@/design-tokens/colors';

export interface ThresholdConfig {
  waspada: number;
  siaga: number;
  krisis: number;
  direction: 'inc' | 'dec';
  unit?: string;
  description?: string;
}

export interface HeatmapCellData {
  value: number | null;
  riskZone: RiskZone;
  formattedValue: string;
}

export interface HeatmapRowData {
  indicator: string;
  label: string;
  pillar: 'risiko' | 'velositas' | 'struktur' | 'infrastruktur' | 'pmkt';
  thresholds: ThresholdConfig | null;
  periods: Record<string, HeatmapCellData>;
  hasSparkline?: boolean;
}

export interface HeatmapData {
  version: 'nb' | 'pmkt';
  simulationId: string;
  periods: string[];
  rows: HeatmapRowData[];
  overallRiskZone: RiskZone;
  generatedAt: string;
}

export interface HeatmapSection {
  id: string;
  label: string;
  pillar: string;
  color: string;
  rows: HeatmapRowData[];
}
