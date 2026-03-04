"""
Python/Dash prototype dashboard — Phase 1 throwaway.

This is a rapid prototype for stakeholder demos before the React dashboard is ready.
See Section 8.1.2 of the spec for context.

Production dashboard: src/frontend/ (React 18 + TypeScript)
"""
from __future__ import annotations

try:
    import dash
    from dash import dcc, html, Input, Output, callback
    import plotly.graph_objects as go
    import plotly.express as px
    DASH_AVAILABLE = True
except ImportError:
    DASH_AVAILABLE = False

import pandas as pd
import numpy as np
from pathlib import Path

# Historical calibration data (Jan-25 to Jan-26)
HISTORICAL = {
    "periods": ["Jan-25","Feb-25","Mar-25","Apr-25","May-25","Jun-25",
                "Jul-25","Aug-25","Sep-25","Oct-25","Nov-25","Dec-25","Jan-26"],
    "tor":     [1.77,1.69,1.84,2.56,2.70,2.74,1.79,1.43,1.39,1.32,1.21,1.46,1.31],
    "tor_adj": [1.19,1.24,1.40,1.78,1.77,1.65,1.37,1.34,1.35,1.20,1.08,1.38,1.13],
    "qr":      [4.84,5.24,4.54,4.02,4.05,3.95,4.90,4.76,4.96,5.47,5.93,4.75,None],
    "ad":      [74.07,72.45,73.27,70.75,71.45,72.68,75.05,73.49,73.46,73.94,72.89,76.88,74.71],
    "awd":     [2.32,2.24,2.38,2.31,2.19,2.58,2.84,2.55,2.89,3.24,2.90,3.16,2.85],
    "su":      [23.37,22.42,25.18,25.14,25.08,25.70,23.17,24.36,24.39,23.97,24.04,27.00,23.89],
}

THRESHOLDS = {
    "tor":   {"waspada": 1.36, "siaga": 2.19, "krisis": 3.03, "direction": "inc"},
    "ad":    {"waspada": 65.80, "siaga": 63.18, "krisis": 60.55, "direction": "dec"},
    "awd":   {"waspada": 2.29, "siaga": 2.14, "krisis": 1.98, "direction": "dec"},
    "qr":    {"waspada": 4.21, "siaga": 3.98, "krisis": 2.74, "direction": "dec"},
    "su":    {"waspada": 26.94, "siaga": 27.99, "krisis": 29.56, "direction": "inc"},
}

RISK_COLORS = {
    "normal":  "#FFFFFF",
    "waspada": "#FFFF00",
    "siaga":   "#FF69B4",
    "krisis":  "#FF0000",
}


def classify_risk(value: float | None, indicator: str) -> str:
    if value is None:
        return "normal"
    t = THRESHOLDS.get(indicator)
    if t is None:
        return "normal"
    if t["direction"] == "inc":
        if value < t["waspada"]:  return "normal"
        if value < t["siaga"]:    return "waspada"
        if value < t["krisis"]:   return "siaga"
        return "krisis"
    else:
        if value > t["waspada"]:  return "normal"
        if value > t["siaga"]:    return "waspada"
        if value > t["krisis"]:   return "siaga"
        return "krisis"


def make_threshold_line_chart(indicator: str, simulated: list[float | None] | None = None) -> "go.Figure":
    """Create a Plotly chart with threshold bands for one indicator."""
    if not DASH_AVAILABLE:
        raise ImportError("plotly is required for this function")

    periods = HISTORICAL["periods"]
    hist_values = HISTORICAL.get(indicator, [])
    sim_values = simulated or hist_values

    t = THRESHOLDS.get(indicator, {})
    w, s, k = t.get("waspada", 0), t.get("siaga", 0), t.get("krisis", 0)
    direction = t.get("direction", "inc")

    fig = go.Figure()

    # Threshold bands
    all_vals = [v for v in sim_values if v is not None] + [w, s, k]
    y_max = max(all_vals) * 1.15 if all_vals else 10
    y_min = min(all_vals) * 0.85 if all_vals else 0

    if direction == "inc":
        band_defs = [(y_min, w, "white"), (w, s, RISK_COLORS["waspada"]),
                     (s, k, RISK_COLORS["siaga"]), (k, y_max, RISK_COLORS["krisis"])]
    else:
        band_defs = [(k, s, RISK_COLORS["siaga"]), (s, w, RISK_COLORS["waspada"]),
                     (w, y_max, "white"), (y_min, k, RISK_COLORS["krisis"])]

    for y0, y1, color in band_defs:
        fig.add_hrect(y0=y0, y1=y1, fillcolor=color, opacity=0.12, line_width=0)

    # Threshold lines
    for level, color, label in [(w, "#CCCC00", "W"), (s, "#FF69B4", "S"), (k, "#FF0000", "K")]:
        fig.add_hline(y=level, line_dash="dash", line_color=color,
                      annotation_text=label, annotation_position="right")

    # Historical series
    fig.add_trace(go.Scatter(
        x=periods, y=hist_values, name="Historical",
        line=dict(color="#999", dash="dash", width=1.5), mode="lines",
    ))

    # Simulated series with risk-colored markers
    marker_colors = [RISK_COLORS[classify_risk(v, indicator)] if v is not None else "#999" for v in sim_values]
    fig.add_trace(go.Scatter(
        x=periods, y=sim_values, name="Simulated",
        line=dict(color="#003366", width=2),
        mode="lines+markers",
        marker=dict(color=marker_colors, size=7, line=dict(color="white", width=1.5)),
    ))

    fig.update_layout(
        template="plotly_white",
        height=380,
        margin=dict(l=50, r=80, t=30, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1),
        yaxis=dict(range=[y_min, y_max]),
    )
    return fig


def build_heatmap_table(sim_data: dict | None = None) -> "pd.DataFrame":
    """Build the heatmap data as a DataFrame for table rendering."""
    data = sim_data or HISTORICAL
    rows = []
    for indicator in ["tor", "ad", "awd", "qr", "su"]:
        values = data.get(indicator, [])
        row = {"Indikator": indicator.upper()}
        t = THRESHOLDS.get(indicator, {})
        row["Waspada"] = t.get("waspada", "")
        row["Siaga"] = t.get("siaga", "")
        row["Krisis"] = t.get("krisis", "")
        for p, v in zip(data["periods"], values):
            row[p] = v
        rows.append(row)
    return pd.DataFrame(rows)


def create_dash_app(debug: bool = False) -> "dash.Dash":
    """Create and configure the Dash prototype application."""
    if not DASH_AVAILABLE:
        raise ImportError(
            "Dash is not installed. Install with: pip install dash plotly"
        )

    app = dash.Dash(
        __name__,
        title="FMI-SimEngine Prototype",
        meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
    )

    INDICATORS = ["tor", "tor_adj", "ad", "awd", "qr", "su"]

    app.layout = html.Div([
        # Header
        html.Div([
            html.H1("FMI-SimEngine", style={"color": "white", "margin": 0, "fontSize": "20px"}),
            html.Span("Heatmap Subprotokol SP — Prototype",
                      style={"color": "#8FAEC1", "fontSize": "13px"}),
        ], style={"backgroundColor": "#003366", "padding": "12px 20px", "display": "flex",
                  "alignItems": "center", "gap": "16px"}),

        # Controls
        html.Div([
            html.Label("Indikator:", style={"fontSize": "12px", "fontWeight": "600"}),
            dcc.Dropdown(
                id="indicator-select",
                options=[{"label": i.upper(), "value": i} for i in INDICATORS],
                value="tor",
                clearable=False,
                style={"width": "200px", "fontSize": "12px"},
            ),
        ], style={"display": "flex", "alignItems": "center", "gap": "10px",
                  "padding": "12px 20px", "backgroundColor": "#f5f5f5",
                  "borderBottom": "1px solid #ddd"}),

        # Chart
        html.Div([
            dcc.Graph(id="threshold-chart", config={"displayModeBar": False}),
        ], style={"padding": "0 20px"}),

        # Stats
        html.Div(id="stats-panel", style={"padding": "12px 20px"}),

        # Heatmap Table (simplified)
        html.Div([
            html.H3("Heatmap Ringkasan", style={"fontSize": "14px", "fontWeight": "700",
                                                  "color": "#003366", "marginBottom": "8px"}),
            html.P("(Run simulation to see full heatmap — this is demo data)",
                   style={"fontSize": "11px", "color": "#999", "marginBottom": "8px"}),
        ], style={"padding": "0 20px 20px"}),

        # Footer
        html.Div([
            html.P("FMI-SimEngine v1.0 — Internal — Bank Indonesia",
                   style={"fontSize": "10px", "color": "#999", "textAlign": "center", "margin": 0}),
        ], style={"padding": "8px", "borderTop": "1px solid #ddd", "backgroundColor": "#f5f5f5"}),
    ], style={"fontFamily": "'IBM Plex Sans', 'Segoe UI', sans-serif", "minHeight": "100vh"})

    @callback(
        Output("threshold-chart", "figure"),
        Output("stats-panel", "children"),
        Input("indicator-select", "value"),
    )
    def update_chart(indicator: str):
        fig = make_threshold_line_chart(indicator)
        values = [v for v in HISTORICAL.get(indicator, []) if v is not None]
        stats = html.Div([
            html.Span(f"Mean: {np.mean(values):.3f}", style={"marginRight": "20px"}),
            html.Span(f"Std: {np.std(values):.3f}", style={"marginRight": "20px"}),
            html.Span(f"Min: {min(values):.3f}", style={"marginRight": "20px"}),
            html.Span(f"Max: {max(values):.3f}"),
        ], style={"fontSize": "11px", "color": "#555", "backgroundColor": "#f9f9f9",
                  "padding": "8px 12px", "borderRadius": "4px"})
        return fig, stats

    return app


def run_prototype(host: str = "127.0.0.1", port: int = 8050, debug: bool = False) -> None:
    """Run the Dash prototype dashboard."""
    app = create_dash_app(debug=debug)
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    run_prototype(debug=True)
