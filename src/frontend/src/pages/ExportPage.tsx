import { FileText, Table, Image, Download } from 'lucide-react';

const EXPORT_OPTIONS = [
  { icon: FileText, label: 'PDF Report', desc: 'Full dashboard snapshot (A3 landscape, 2x resolution)', format: 'pdf' },
  { icon: Table, label: 'Excel Heatmap', desc: 'BI-format identical Excel workbook with conditional formatting', format: 'excel' },
  { icon: Image, label: 'PNG Charts', desc: 'Individual chart exports at high resolution', format: 'png' },
  { icon: Download, label: 'Raw Data', desc: 'Parquet / JSON simulation results for further analysis', format: 'data' },
];

export default function ExportPage() {
  return (
    <div className="space-y-4">
      <div className="bg-white rounded-lg border border-gray-200 px-4 py-3">
        <h2 className="font-bold text-gray-900 text-base">Report Generation & Export</h2>
        <p className="text-xs text-gray-500 mt-0.5">Export simulation results in BI-compatible formats</p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {EXPORT_OPTIONS.map(({ icon: Icon, label, desc, format }) => (
          <button
            key={format}
            className="bg-white rounded-lg border border-gray-200 p-4 text-left hover:border-[#003366] hover:shadow-sm transition-all group"
          >
            <div className="flex items-start gap-3">
              <div className="p-2.5 bg-gray-100 rounded-lg group-hover:bg-[#003366] transition-colors">
                <Icon size={18} className="text-gray-600 group-hover:text-white transition-colors" />
              </div>
              <div>
                <div className="font-semibold text-gray-800 text-sm">{label}</div>
                <p className="text-xs text-gray-500 mt-0.5">{desc}</p>
              </div>
            </div>
          </button>
        ))}
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-xs text-blue-800">
        <strong>Note:</strong> Run a simulation first to enable full export capabilities. 
        Demo exports use historical calibration data.
      </div>
    </div>
  );
}
