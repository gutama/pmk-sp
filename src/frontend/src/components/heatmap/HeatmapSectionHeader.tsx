interface HeatmapSectionHeaderProps {
  label: string;
  colSpan: number;
  level: 'primary' | 'secondary' | 'pmkt';
}

const COLORS = {
  primary:   { bg: '#003366', text: '#FFFFFF' },
  secondary: { bg: '#336699', text: '#FFFFFF' },
  pmkt:      { bg: '#7B5B00', text: '#FFFFFF' },
};

export default function HeatmapSectionHeader({ label, colSpan, level }: HeatmapSectionHeaderProps) {
  const { bg, text } = COLORS[level];
  return (
    <tr>
      <td
        colSpan={colSpan}
        className="px-3 py-1.5 font-bold"
        style={{
          backgroundColor: bg,
          color: text,
          fontSize: '10px',
          letterSpacing: '0.05em',
          textTransform: 'uppercase',
        }}
      >
        {label}
      </td>
    </tr>
  );
}
