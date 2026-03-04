import { create } from 'zustand';
import { SimulationConfig, SimulationStatus } from '@/types/simulation';

interface SimulationState {
  config: SimulationConfig;
  status: SimulationStatus | null;
  activeSimulationId: string | null;
  completedSimulations: string[];

  setConfig: (config: Partial<SimulationConfig>) => void;
  setStatus: (status: SimulationStatus) => void;
  setActiveSimulation: (id: string | null) => void;
  addCompletedSimulation: (id: string) => void;
  reset: () => void;
}

const DEFAULT_CONFIG: SimulationConfig = {
  nBanks: 140,
  nDays: 30,
  scenario: 'baseline',
  scenarioParams: {},
  seed: 42,
  systems: ['rtgs', 'fast', 'raja'],
  tickIntervalMin: 1,
};

export const useSimulationStore = create<SimulationState>((set) => ({
  config: DEFAULT_CONFIG,
  status: null,
  activeSimulationId: null,
  completedSimulations: [],

  setConfig: (partial) =>
    set((state) => ({ config: { ...state.config, ...partial } })),

  setStatus: (status) => set({ status }),

  setActiveSimulation: (id) => set({ activeSimulationId: id }),

  addCompletedSimulation: (id) =>
    set((state) => ({
      completedSimulations: [...state.completedSimulations, id],
    })),

  reset: () =>
    set({ config: DEFAULT_CONFIG, status: null, activeSimulationId: null }),
}));
