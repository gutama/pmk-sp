export const RISK_COLORS = {
  normal:  { bg: '#FFFFFF', text: '#1A1A1A', border: '#E0E0E0' },
  waspada: { bg: '#FFFF00', text: '#1A1A1A', border: '#E6E600' },
  siaga:   { bg: '#FF69B4', text: '#FFFFFF', border: '#FF1493' },
  krisis:  { bg: '#FF0000', text: '#FFFFFF', border: '#CC0000' },
} as const;

export const HEADER_COLORS = {
  primary:   '#003366',
  secondary: '#336699',
  tertiary:  '#4A90D9',
} as const;

export const THRESHOLD_BAND_COLORS = {
  normal:  'rgba(255, 255, 255, 0.0)',
  waspada: 'rgba(255, 255, 0, 0.12)',
  siaga:   'rgba(255, 105, 180, 0.12)',
  krisis:  'rgba(255, 0, 0, 0.10)',
} as const;

export const SYSTEM_COLORS = {
  bi_rtgs: '#003366',
  bi_fast: '#E63946',
  raja:    '#2A9D8F',
} as const;

export const NETWORK_COLORS = {
  core_bank:      '#003366',
  periphery_bank: '#8FAEC1',
  stressed_bank:  '#FF69B4',
  failed_bank:    '#FF0000',
} as const;

export type RiskZone = 'normal' | 'waspada' | 'siaga' | 'krisis';

export function getRiskColor(zone: RiskZone) {
  return RISK_COLORS[zone];
}

export function getRiskBgClass(zone: RiskZone): string {
  const map: Record<RiskZone, string> = {
    normal:  'risk-normal',
    waspada: 'risk-waspada',
    siaga:   'risk-siaga',
    krisis:  'risk-krisis',
  };
  return map[zone];
}
