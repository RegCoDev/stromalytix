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
    Build a scatter plot showing users construct vs. published benchmarks.

    Args:
        report: VarianceReport containing benchmark ranges and construct values

    Returns:
        Plotly Figure with scatter plot of parameters and ranges
    """
    parameters = []
    min_values = []
    max_values = []
    user_values = []
    x_positions = []

    x_pos = 0
    for param, benchmark_data in report.benchmark_ranges.items():
        if isinstance(benchmark_data, dict) and "min" in benchmark_data and "max" in benchmark_data:
            parameters.append(param)
            min_values.append(benchmark_data["min"])
            max_values.append(benchmark_data["max"])

            # Get users value from construct profile
            user_val = getattr(report.construct_profile, param, None)
            if user_val is not None:
                user_values.append(user_val)
            else:
                user_values.append(None)

            x_positions.append(x_pos)
            x_pos += 1

    # Create figure
    fig = go.Figure()

    # Add benchmark range bands (min to max)
    fig.add_trace(
        go.Scatter(
            x=x_positions,
            y=min_values,
            mode="lines",
            line=dict(width=0),
            showlegend=False,
            hoverinfo="skip",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=x_positions,
            y=max_values,
            mode="lines",
            line=dict(width=0),
            fillcolor=f"rgba(74, 158, 255, 0.2)",
            fill="tonexty",
            name="Published Range",
            hovertemplate="<b>%{text}</b><br>Range: %{y:.2f}<extra></extra>",
            text=parameters,
        )
    )

    # Add user construct points as large stars
    fig.add_trace(
        go.Scatter(
            x=x_positions,
            y=user_values,
            mode="markers",
            marker=dict(
                size=15,
                symbol="star",
                color=DARK_THEME["accent_green"],
                line=dict(color=DARK_THEME["text"], width=2),
            ),
            name="Your Construct",
            hovertemplate="<b>%{text}</b><br>Your Value: %{y:.2f}<extra></extra>",
            text=parameters,
        )
    )

    # Add benchmark center line (average of min and max)
    center_values = [(min_val + max_val) / 2 for min_val, max_val in zip(min_values, max_values)]
    fig.add_trace(
        go.Scatter(
            x=x_positions,
            y=center_values,
            mode="lines",
            line=dict(color=DARK_THEME["accent_blue"], width=2, dash="dot"),
            name="Benchmark Center",
            hovertemplate="<b>%{text}</b><br>Center: %{y:.2f}<extra></extra>",
            text=parameters,
        )
    )

    # Update layout with dark theme
    fig.update_layout(
        title={
            "text": "Your Protocol vs. Published Benchmarks",
            "font": {"size": 20, "color": DARK_THEME["text"]},
            "x": 0.5,
            "xanchor": "center",
        },
        xaxis=dict(
            title="Parameter",
            title_font=dict(color=DARK_THEME["text"], size=12),
            tickfont=dict(color=DARK_THEME["text"], size=10),
            ticktext=parameters,
            tickvals=x_positions,
            gridcolor=DARK_THEME["grid"],
            showgrid=True,
        ),
        yaxis=dict(
            title="Normalized Values",
            title_font=dict(color=DARK_THEME["text"], size=12),
            tickfont=dict(color=DARK_THEME["text"], size=10),
            gridcolor=DARK_THEME["grid"],
            showgrid=True,
        ),
        paper_bgcolor=DARK_THEME["paper"],
        plot_bgcolor=DARK_THEME["background"],
        font=dict(color=DARK_THEME["text"], family="Arial, sans-serif"),
        hovermode="x unified",
        legend=dict(
            x=0.98,
            y=0.98,
            bgcolor="rgba(17, 17, 17, 0.8)",
            bordercolor=DARK_THEME["grid"],
            borderwidth=1,
            font=dict(color=DARK_THEME["text"], size=11),
        ),
        margin=dict(l=100, r=50, t=100, b=100),
        height=500,
    )

    return fig