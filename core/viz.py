"""
Plotly Visualization Functions for Stromalytix

Generates interactive charts for variance analysis and protocol comparison.
"""

from typing import Dict, List

import plotly.graph_objects as go

from core.models import VarianceReport


# Dark Theme Configuration
DARK_THEME = {
    "background": "#0a0a0a",
    "paper": "#111111",
    "text": "#e0e0e0",
    "accent_green": "#00ff88",
    "grid": "#222222",
    "accent_blue": "#4a9eff",
    "accent_yellow": "#ffd700",
    "accent_red": "#ff4444",
}


def build_radar_chart(report: VarianceReport) -> go.Figure:
    """
    Build a radar chart comparing users construct to literature benchmarks.

    Args:
        report: VarianceReport containing deviation scores and construct profile

    Returns:
        Plotly Figure with radar chart showing construct vs. benchmark
    """
    # Define radar axes in order
    radar_axes = [
        "stiffness_kpa",
        "porosity_percent",
        "cell_density",
        "physiological_relevance",
        "phenotype_fidelity",
    ]

    # Extract and normalize deviation scores to 0-1 scale
    # Deviation scores are -1 to 1, so we map: -1 -> 0, 0 -> 0.5, 1 -> 1
    user_values = []
    benchmark_values = []

    for axis in radar_axes:
        deviation = report.deviation_scores.get(axis, 0)
        # Normalize from [-1, 1] to [0, 1]
        normalized = (deviation + 1) / 2
        user_values.append(normalized)
        # Benchmark is always at 0.5 (center = perfect match)
        benchmark_values.append(0.5)

    # Create figure
    fig = go.Figure()

    # Add user construct trace (filled, green)
    fig.add_trace(
        go.Scatterpolar(
            r=user_values,
            theta=radar_axes,
            fill="toself",
            fillcolor=DARK_THEME["accent_green"],
            opacity=0.3,
            line=dict(color=DARK_THEME["accent_green"], width=2),
            name="Your Construct",
            hovertemplate="<b>%{theta}</b><br>Value: %{r:.2f}<extra></extra>",
        )
    )

    # Add benchmark trace (dashed line, blue)
    fig.add_trace(
        go.Scatterpolar(
            r=benchmark_values,
            theta=radar_axes,
            fill=None,
            line=dict(
                color=DARK_THEME["accent_blue"],
                width=2,
                dash="dash",
            ),
            name="Literature Benchmark",
            hovertemplate="<b>%{theta}</b><br>Benchmark: %{r:.2f}<extra></extra>",
        )
    )

    # Update layout with dark theme
    fig.update_layout(
        title={
            "text": "Protocol Deviation Radar",
            "font": {"size": 20, "color": DARK_THEME["text"]},
            "x": 0.5,
            "xanchor": "center",
        },
        polar=dict(
            bgcolor=DARK_THEME["background"],
            radialaxis=dict(
                visible=True,
                range=[0, 1],
                tickfont=dict(color=DARK_THEME["text"], size=10),
                gridcolor=DARK_THEME["grid"],
                linecolor=DARK_THEME["grid"],
            ),
            angularaxis=dict(
                tickfont=dict(color=DARK_THEME["text"], size=11),
                gridcolor=DARK_THEME["grid"],
                linecolor=DARK_THEME["grid"],
            ),
        ),
        paper_bgcolor=DARK_THEME["paper"],
        plot_bgcolor=DARK_THEME["background"],
        font=dict(color=DARK_THEME["text"], family="Arial, sans-serif"),
        hovermode="closest",
        legend=dict(
            x=0.98,
            y=0.98,
            bgcolor="rgba(17, 17, 17, 0.8)",
            bordercolor=DARK_THEME["grid"],
            borderwidth=1,
            font=dict(color=DARK_THEME["text"], size=11),
        ),
        margin=dict(l=100, r=100, t=100, b=100),
        height=600,
    )

    return fig

def build_risk_scorecard(report: VarianceReport) -> go.Figure:
    """
    Build a horizontal bar chart showing risk assessment by parameter.

    Args:
        report: VarianceReport containing risk flags and deviation scores

    Returns:
        Plotly Figure with horizontal bar chart and benchmark baseline
    """
    parameters = list(report.risk_flags.keys())
    risk_statuses = list(report.risk_flags.values())
    deviation_scores = [
        report.deviation_scores.get(param, 0) for param in parameters
    ]

    # Convert deviation scores to percentages (-100% to +100%)
    x_values = [score * 100 for score in deviation_scores]

    # Map risk status to colors
    color_map = {
        "green": DARK_THEME["accent_green"],
        "yellow": DARK_THEME["accent_yellow"],
        "red": DARK_THEME["accent_red"],
    }
    bar_colors = [color_map.get(status, DARK_THEME["accent_blue"]) for status in risk_statuses]

    # Create figure
    fig = go.Figure()

    # Add horizontal bars
    fig.add_trace(
        go.Bar(
            y=parameters,
            x=x_values,
            orientation="h",
            marker=dict(color=bar_colors, line=dict(color=DARK_THEME["text"], width=1)),
            text=[f"{x:.0f}%" for x in x_values],
            textposition="inside",
            textfont=dict(color=DARK_THEME["background"], size=11, weight="bold"),
            hovertemplate="<b>%{y}</b><br>Deviation: %{x:.1f}%<extra></extra>",
            name="",
        )
    )

    # Add vertical line at x=0 (benchmark center)
    fig.add_vline(
        x=0,
        line_dash="dash",
        line_color=DARK_THEME["grid"],
        line_width=2,
        annotation_text="Benchmark",
        annotation_position="top right",
        annotation_font=dict(color=DARK_THEME["text"], size=10),
    )

    # Update layout with dark theme
    fig.update_layout(
        title={
            "text": "Risk Assessment by Parameter",
            "font": {"size": 20, "color": DARK_THEME["text"]},
            "x": 0.5,
            "xanchor": "center",
        },
        xaxis=dict(
            title="Deviation Score (%)",
            title_font=dict(color=DARK_THEME["text"], size=12),
            tickfont=dict(color=DARK_THEME["text"], size=10),
            gridcolor=DARK_THEME["grid"],
            showgrid=True,
            zeroline=False,
            range=[-100, 100],
        ),
        yaxis=dict(
            title="Parameter",
            title_font=dict(color=DARK_THEME["text"], size=12),
            tickfont=dict(color=DARK_THEME["text"], size=10),
            autorange="reversed",
        ),
        paper_bgcolor=DARK_THEME["paper"],
        plot_bgcolor=DARK_THEME["background"],
        font=dict(color=DARK_THEME["text"], family="Arial, sans-serif"),
        hovermode="y unified",
        showlegend=False,
        margin=dict(l=200, r=50, t=100, b=80),
        height=500,
    )

    return fig

def build_parameter_scatter(report: VarianceReport) -> go.Figure:
    """
    Build a horizontal bullet/range chart comparing the user's protocol
    values against published literature ranges for each parameter.

    Each row is one parameter.  The shaded band is the literature range
    (min-max), a vertical rule marks the optimal/centre value, and a
    diamond marker shows the user's value.  Colour coding comes from
    the risk_flags in the report (green / yellow / red).
    """
    from plotly.subplots import make_subplots

    rows = []
    for param, bench in report.benchmark_ranges.items():
        if not isinstance(bench, dict) or "min" not in bench or "max" not in bench:
            continue
        user_val = getattr(report.construct_profile, param, None)
        unit = bench.get("unit", "")
        optimal = bench.get("optimal", (bench["min"] + bench["max"]) / 2)
        risk = report.risk_flags.get(param, "green")
        rows.append(dict(
            param=param, bmin=bench["min"], bmax=bench["max"],
            optimal=optimal, user=user_val, unit=unit, risk=risk,
        ))

    if not rows:
        fig = go.Figure()
        fig.update_layout(
            paper_bgcolor=DARK_THEME["paper"],
            plot_bgcolor=DARK_THEME["background"],
            annotations=[dict(
                text="No benchmark data available",
                xref="paper", yref="paper", x=0.5, y=0.5,
                showarrow=False,
                font=dict(color=DARK_THEME["text"], size=16),
            )],
        )
        return fig

    n = len(rows)
    fig = make_subplots(
        rows=n, cols=1, shared_xaxes=False,
        vertical_spacing=0.04,
        row_heights=[1] * n,
    )

    risk_color = {
        "green": DARK_THEME["accent_green"],
        "yellow": DARK_THEME["accent_yellow"],
        "red": DARK_THEME["accent_red"],
    }

    for i, r in enumerate(rows, start=1):
        bmin, bmax = r["bmin"], r["bmax"]
        span = bmax - bmin if bmax != bmin else 1.0
        pad = span * 0.25
        lo = bmin - pad
        hi = bmax + pad

        if r["user"] is not None:
            lo = min(lo, r["user"] - pad)
            hi = max(hi, r["user"] + pad)

        fig.add_shape(
            type="rect",
            x0=bmin, x1=bmax, y0=-0.4, y1=0.4,
            fillcolor="rgba(74, 158, 255, 0.25)",
            line=dict(width=0),
            row=i, col=1,
        )

        fig.add_shape(
            type="line",
            x0=r["optimal"], x1=r["optimal"], y0=-0.45, y1=0.45,
            line=dict(color=DARK_THEME["accent_blue"], width=2, dash="dot"),
            row=i, col=1,
        )

        color = risk_color.get(r["risk"], DARK_THEME["accent_blue"])
        if r["user"] is not None:
            fig.add_trace(
                go.Scatter(
                    x=[r["user"]], y=[0],
                    mode="markers+text",
                    marker=dict(
                        size=14, symbol="diamond",
                        color=color,
                        line=dict(color=DARK_THEME["text"], width=1.5),
                    ),
                    text=[f'{r["user"]:.4g}'],
                    textposition="top center",
                    textfont=dict(color=color, size=11),
                    hovertemplate=(
                        f'<b>{r["param"]}</b><br>'
                        f'Your value: {r["user"]:.4g} {r["unit"]}<br>'
                        f'Range: {bmin:.4g} – {bmax:.4g} {r["unit"]}'
                        '<extra></extra>'
                    ),
                    showlegend=False,
                ),
                row=i, col=1,
            )

        label = r["param"].replace("_", " ").title()
        fig.update_yaxes(
            visible=False, range=[-0.6, 0.8], row=i, col=1,
        )
        fig.update_xaxes(
            range=[lo, hi],
            showgrid=False,
            tickfont=dict(color=DARK_THEME["text"], size=9),
            gridcolor=DARK_THEME["grid"],
            row=i, col=1,
        )

        fig.add_annotation(
            x=0, y=0.5,
            xref=f"x{i} domain" if i > 1 else "x domain",
            yref=f"y{i} domain" if i > 1 else "y domain",
            text=f"<b>{label}</b>  <i>({r['unit']})</i>",
            showarrow=False,
            xanchor="left", yanchor="bottom",
            font=dict(color=DARK_THEME["text"], size=12),
        )

    fig.update_layout(
        title={
            "text": "Your Protocol vs. Published Benchmarks",
            "font": {"size": 20, "color": DARK_THEME["text"]},
            "x": 0.5, "xanchor": "center",
        },
        paper_bgcolor=DARK_THEME["paper"],
        plot_bgcolor=DARK_THEME["background"],
        font=dict(color=DARK_THEME["text"], family="Arial, sans-serif"),
        showlegend=False,
        height=max(300, 110 * n),
        margin=dict(l=30, r=30, t=80, b=30),
    )

    return fig