interface ThresholdColumnsProps {
  waspada: number | string | null;
  siaga: number | string | null;
  krisis: number | string | null;
}

export default function ThresholdColumns({ waspada, siaga, krisis }: ThresholdColumnsProps) {
  const fmt = (v: number | string | null) =>
    v == null ? '—' : typeof v === 'number' ? v.toLocaleString() : v;

  return (
    <>
      <td className="text-center text-xs px-2 py-1.5 border-b border-gray-200 bg-yellow-50 tabular-nums font-medium" style={{ fontSize: '11px' }}>
        {fmt(waspada)}
      </td>
      <td className="text-center text-xs px-2 py-1.5 border-b border-gray-200 bg-pink-50 tabular-nums font-medium" style={{ fontSize: '11px' }}>
        {fmt(siaga)}
      </td>
      <td className="text-center text-xs px-2 py-1.5 border-b border-gray-200 bg-red-50 tabular-nums font-medium" style={{ fontSize: '11px' }}>
        {fmt(krisis)}
      </td>
    </>
  );
}
