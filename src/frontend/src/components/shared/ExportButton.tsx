import { useState } from 'react';
import { Download, FileText, Table, Image } from 'lucide-react';
import { useSimulationStore } from '@/stores/simulationStore';

export default function ExportButton() {
  const [open, setOpen] = useState(false);
  const { activeSimulationId } = useSimulationStore();

  const handlePDFExport = async () => {
    setOpen(false);
    try {
      const { default: html2canvas } = await import('html2canvas');
      const { jsPDF } = await import('jspdf');
      const el = document.getElementById('heatmap-nb-container');
      if (!el) return;
      const canvas = await html2canvas(el, { scale: 2 });
      const pdf = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a3' });
      pdf.addImage(canvas.toDataURL(), 'PNG', 10, 10, 400, 200);
      pdf.save(`fmi-simengine-heatmap-${activeSimulationId?.slice(0, 8) ?? 'export'}.pdf`);
    } catch (e) {
      console.error('PDF export failed', e);
    }
  };

  const handleExcelExport = async () => {
    setOpen(false);
    try {
      const XLSX = await import('xlsx');
      const data = [
        ['Indikator', 'Waspada', 'Siaga', 'Krisis', 'Jan-25', 'Feb-25', 'Mar-25', '...'],
        ['TOR', 1.36, 2.19, 3.03, 1.77, 1.69, 1.84, '...'],
      ];
      const ws = XLSX.utils.aoa_to_sheet(data);
      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, ws, 'Heatmap NB');
      XLSX.writeFile(wb, `fmi-simengine-${activeSimulationId?.slice(0, 8) ?? 'export'}.xlsx`);
    } catch (e) {
      console.error('Excel export failed', e);
    }
  };

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-[#003366] text-white rounded hover:bg-[#004080] transition-colors"
      >
        <Download size={13} />
        Export
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-full mt-1 bg-white border border-gray-200 rounded shadow-lg z-50 w-40 py-1">
            <button
              onClick={handlePDFExport}
              className="flex items-center gap-2 w-full px-3 py-2 text-xs hover:bg-gray-50 text-gray-700"
            >
              <FileText size={13} /> PDF Snapshot
            </button>
            <button
              onClick={handleExcelExport}
              className="flex items-center gap-2 w-full px-3 py-2 text-xs hover:bg-gray-50 text-gray-700"
            >
              <Table size={13} /> Excel (BI Format)
            </button>
            <button
              className="flex items-center gap-2 w-full px-3 py-2 text-xs hover:bg-gray-50 text-gray-700"
            >
              <Image size={13} /> PNG Chart
            </button>
          </div>
        </>
      )}
    </div>
  );
}
