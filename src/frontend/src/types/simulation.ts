export interface SimulationConfig {
  nBanks: number;
  nDays: number;
  scenario: string;
  scenarioParams: Record<string, unknown>;
  seed: number;
  systems: string[];
  tickIntervalMin: number;
}

export interface SimulationStatus {
  simulationId: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progressPct: number;
  currentDay: number;
  totalDays: number;
  startedAt?: string;
  completedAt?: string;
  errorMessage?: string;
}

export interface DayMetrics {
  day: number;
  settledCount: number;
  failedCount: number;
  queuedCount: number;
  totalValueSettled: number;
  tor: number;
  queueRatio: number;
  averageDegree: number;
}
