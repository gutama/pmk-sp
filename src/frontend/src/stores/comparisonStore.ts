import { create } from 'zustand';

interface ComparisonState {
  selectedSimulations: string[];
  comparisonData: Record<string, unknown> | null;

  addSimulation: (id: string) => void;
  removeSimulation: (id: string) => void;
  clearComparison: () => void;
  setComparisonData: (data: Record<string, unknown>) => void;
}

export const useComparisonStore = create<ComparisonState>((set) => ({
  selectedSimulations: [],
  comparisonData: null,

  addSimulation: (id) =>
    set((state) => ({
      selectedSimulations: [...new Set([...state.selectedSimulations, id])],
    })),

  removeSimulation: (id) =>
    set((state) => ({
      selectedSimulations: state.selectedSimulations.filter((s) => s !== id),
    })),

  clearComparison: () => set({ selectedSimulations: [], comparisonData: null }),

  setComparisonData: (data) => set({ comparisonData: data }),
}));
