export interface NetworkNode {
  id: string;
  tier: 'core' | 'periphery';
  degree: number;
  weightedDegree: number;
  systemicImportance: number;
  riskZone: string;
  x?: number;
  y?: number;
}

export interface NetworkEdge {
  source: string;
  target: string;
  weight: number;
  transactionCount: number;
  value: number;
}

export interface NetworkData {
  simulationId: string;
  period: string;
  system: string;
  nodes: NetworkNode[];
  edges: NetworkEdge[];
  metrics: {
    avgDegree: number;
    avgWeightedDegree: number;
    density: number;
    nodeCount: number;
    edgeCount: number;
  };
}

export interface ContagionRound {
  roundNum: number;
  shockedBanks: string[];
  affectedBanks: string[];
  cumulativeLossPct: number;
  debtRankScore: number;
  newlyFailed: string[];
}

export interface ContagionData {
  simulationId: string;
  initialBank: string;
  totalRounds: number;
  rounds: ContagionRound[];
  finalDebtRank: number;
  totalBanksAffected: number;
  systemicImportance: Record<string, number>;
}
