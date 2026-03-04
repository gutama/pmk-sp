export function formatValue(value: number | null, indicator: string): string {
  if (value === null) return 'TBU';

  const pctIndicators = new Set([
    'system_availability', 'throughput_zona3', 'system_utilization',
    'stability_index_provider_fast', 'stability_index_participant_fast',
    'availability_rtgs',
  ]);

  const intIndicators = new Set([
    'unsettled_banks', 'avg_koneksi', 'volatility_interconnectedness',
    'unsettled_rtgs_dana', 'reject_fast_dana', 'unsettled_rtgs_nondana',
  ]);

  if (pctIndicators.has(indicator)) return `${value.toFixed(2)}%`;
  if (intIndicators.has(indicator)) return value.toLocaleString('id-ID', { maximumFractionDigits: 0 });
  return value.toFixed(2);
}

export function formatPeriodLabel(period: string): string {
  const map: Record<string, string> = {
    '2025M1': 'Jan-25', '2025M2': 'Feb-25', '2025M3': 'Mar-25',
    '2025M4': 'Apr-25', '2025M5': 'May-25', '2025M6': 'Jun-25',
    '2025M7': 'Jul-25', '2025M8': 'Aug-25', '2025M9': 'Sep-25',
    '2025M10': 'Oct-25', '2025M11': 'Nov-25', '2025M12': 'Dec-25',
    '2026M1': 'Jan-26',
  };
  return map[period] ?? period;
}

export function formatCurrency(value: number): string {
  if (value >= 1e12) return `Rp ${(value / 1e12).toFixed(1)}T`;
  if (value >= 1e9)  return `Rp ${(value / 1e9).toFixed(1)}M`;
  if (value >= 1e6)  return `Rp ${(value / 1e6).toFixed(1)}jt`;
  return `Rp ${value.toLocaleString('id-ID')}`;
}
