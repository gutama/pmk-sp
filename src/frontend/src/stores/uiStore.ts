import { create } from 'zustand';

interface UIState {
  selectedTab: 'nb' | 'pmkt';
  selectedIndicator: string;
  selectedSystem: string;
  selectedPeriod: string;
  sidebarOpen: boolean;
  colorBlindMode: boolean;

  setTab: (tab: 'nb' | 'pmkt') => void;
  setIndicator: (indicator: string) => void;
  setSystem: (system: string) => void;
  setPeriod: (period: string) => void;
  toggleSidebar: () => void;
  toggleColorBlindMode: () => void;
}

export const useUIStore = create<UIState>((set) => ({
  selectedTab: 'nb',
  selectedIndicator: 'tor',
  selectedSystem: 'rtgs',
  selectedPeriod: 'latest',
  sidebarOpen: true,
  colorBlindMode: false,

  setTab: (tab) => set({ selectedTab: tab }),
  setIndicator: (indicator) => set({ selectedIndicator: indicator }),
  setSystem: (system) => set({ selectedSystem: system }),
  setPeriod: (period) => set({ selectedPeriod: period }),
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  toggleColorBlindMode: () => set((state) => ({ colorBlindMode: !state.colorBlindMode })),
}));
