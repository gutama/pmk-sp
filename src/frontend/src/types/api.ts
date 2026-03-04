export interface ApiError {
  detail: string;
  status: number;
}

export interface TimeSeriesPoint {
  period: string;
  value: number | null;
  riskZone: string;
}

export interface TimeSeriesData {
  simulationId: string;
  indicator: string;
  simulated: TimeSeriesPoint[];
  historical: TimeSeriesPoint[];
  thresholds: { waspada: number; siaga: number; krisis: number };
  direction: 'inc' | 'dec';
  statistics: { mean: number; std: number; min: number; max: number };
}
