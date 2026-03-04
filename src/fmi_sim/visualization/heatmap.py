"""Heatmap rendering utilities (Python/Dash prototype)."""
from __future__ import annotations
from typing import Any
import pandas as pd


RISK_COLORS = {
    "normal":  ("#FFFFFF", "#1A1A1A"),
    "waspada": ("#FFFF00", "#1A1A1A"),
    "siaga":   ("#FF69B4", "#FFFFFF"),
    "krisis":  ("#FF0000", "#FFFFFF"),
}


def classify_risk(value: float | None, thresholds: dict, direction: str) -> str:
    """Classify a value into a risk zone."""
    if value is None:
        return "normal"
    w, s, k = thresholds.get("waspada", 0), thresholds.get("siaga", 0), thresholds.get("krisis", 0)
    if direction == "inc":
        if value < w: return "normal"
        if value < s: return "waspada"
        if value < k: return "siaga"
        return "krisis"
    else:
        if value > w: return "normal"
        if value > s: return "waspada"
        if value > k: return "siaga"
        return "krisis"


def render_heatmap_html(heatmap_data: dict[str, Any], output_path: str | None = None) -> str:
    """
    Render the heatmap as an HTML table matching BI slide #13 format.

    Args:
        heatmap_data: Dict with 'indicators', 'periods', 'values', 'thresholds'
        output_path: Optional path to write HTML file

    Returns:
        HTML string
    """
    indicators = heatmap_data.get("indicators", [])
    periods = heatmap_data.get("periods", [])
    values = heatmap_data.get("values", {})
    thresholds = heatmap_data.get("thresholds", {})

    css = """
    <style>
      body { font-family: 'IBM Plex Sans', 'Segoe UI', sans-serif; }
      table { border-collapse: collapse; font-size: 11px; }
      th { padding: 6px 8px; font-size: 10px; text-align: center; }
      td { padding: 5px 8px; text-align: center; border-bottom: 1px solid #E0E0E0; }
      .indicator-col { text-align: left; min-width: 200px; background: #fff; font-weight: normal; }
      .section-header { background: #003366; color: white; font-weight: bold; text-align: left; padding: 6px 8px; }
      .sub-header { background: #336699; color: white; text-align: left; padding: 4px 8px; }
    </style>
    """

    rows_html = []
    for ind in indicators:
        t = thresholds.get(ind, {})
        direction = t.get("direction", "inc")
        ind_values = values.get(ind, [])
        cells = []
        for p, v in zip(periods, ind_values):
            zone = classify_risk(v, t, direction)
            bg, fg = RISK_COLORS.get(zone, ("#fff", "#000"))
            fmt_v = "TBU" if v is None else f"{v:.2f}"
            cells.append(f'<td style="background:{bg};color:{fg}">{fmt_v}</td>')
        row = (
            f'<tr>'
            f'<td class="indicator-col">{ind.replace("_", " ").title()}</td>'
            f'<td>{t.get("waspada", "—")}</td>'
            f'<td>{t.get("siaga", "—")}</td>'
            f'<td>{t.get("krisis", "—")}</td>'
            f'{"".join(cells)}'
            f'</tr>'
        )
        rows_html.append(row)

    period_headers = "".join(
        f'<th style="background:#003366;color:white">{p}</th>' for p in periods
    )

    html = f"""
<!DOCTYPE html>
<html lang="id">
<head><meta charset="UTF-8"><title>Heatmap Subprotokol SP</title>{css}</head>
<body>
<h2 style="color:#003366;font-size:16px">Heatmap Subprotokol SP — Simulasi FMI-SimEngine</h2>
<table>
  <thead>
    <tr>
      <th class="indicator-col" style="background:#003366;color:white">Indikator</th>
      <th style="background:#F5F0A0;color:#333">Waspada</th>
      <th style="background:#FFB6C1;color:#333">Siaga</th>
      <th style="background:#FFB3B3;color:#333">Krisis</th>
      {period_headers}
    </tr>
  </thead>
  <tbody>
    {"".join(rows_html)}
  </tbody>
</table>
<p style="font-size:10px;color:#999;margin-top:8px">FMI-SimEngine v1.0 — Internal — Bank Indonesia</p>
</body>
</html>
"""

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

    return html
