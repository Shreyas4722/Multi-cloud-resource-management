"""Shared visual constants for the dashboard.

Pure presentation -- color and layout constants only. No business logic and
no data access lives here.
"""

from __future__ import annotations

PROVIDER_COLORS = {
    "aws": "#F59E0B",
    "azure": "#3B82F6",
    "gcp": "#A78BFA",
    "demo": "#64748B",
    "unassigned": "#64748B",
}

SEVERITY_COLORS = {
    "high": "#EF4444",
    "medium": "#F59E0B",
    "low": "#94A3B8",
}

ACCENT = "#22C55E"
DESTRUCTIVE = "#EF4444"
MUTED = "#94A3B8"
GRID_COLOR = "#334155"

PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#F8FAFC"),
    margin=dict(l=10, r=10, t=40, b=10),
    legend=dict(bgcolor="rgba(0,0,0,0)"),
)


def apply_layout(fig):
    """Apply the shared dark-theme layout to a Plotly figure, in place."""
    fig.update_layout(**PLOTLY_LAYOUT)
    fig.update_xaxes(gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR)
    fig.update_yaxes(gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR)
    return fig


def color_for_provider(provider: str) -> str:
    return PROVIDER_COLORS.get(provider, MUTED)


def color_for_severity(severity: str) -> str:
    return SEVERITY_COLORS.get(severity, MUTED)
