export default function ComparisonPage() {
  return (
    <div className="space-y-4">
      <div className="bg-white rounded-lg border border-gray-200 px-4 py-3">
        <h2 className="font-bold text-gray-900 text-base">Simulated vs Historical Comparison</h2>
        <p className="text-xs text-gray-500 mt-0.5">Compare simulation output against historical BI heatmap data</p>
      </div>
      <div className="bg-white rounded-lg border border-gray-200 p-8 flex items-center justify-center text-gray-400">
        <div className="text-center">
          <div className="text-4xl mb-3">📊</div>
          <p className="font-medium">Run a simulation to enable comparison</p>
          <p className="text-sm mt-1">Side-by-side heatmap comparison will appear here</p>
        </div>
      </div>
    </div>
  );
}
