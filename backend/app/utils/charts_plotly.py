"""
Charts Helper with Plotly - Modern Power BI style charts
Uses Plotly for beautiful, interactive charts with WebEngineView
"""

from typing import Any, Dict, List, Optional
import json

import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Power BI inspired color palette
COLORS = {
    "primary": "#5B9BD5",      # Blue
    "secondary": "#ED7D31",    # Orange
    "success": "#70AD47",      # Green
    "danger": "#FF5733",       # Red
    "warning": "#FFC000",      # Yellow
    "info": "#4472C4",         # Dark Blue
    "purple": "#7030A0",       # Purple
    "teal": "#00B0F0",         # Teal
}

PALETTE = [
    "#5B9BD5", "#ED7D31", "#70AD47", "#FFC000", 
    "#4472C4", "#7030A0", "#00B0F0", "#C55A11",
    "#538135", "#203864", "#833C0C", "#0D0D0D"
]

# Dark theme colors
DARK_LAYOUT = {
    "paper_bgcolor": "#1a1a2e",
    "plot_bgcolor": "#1a1a2e",
    "font": {"color": "#ffffff", "family": "Segoe UI, Arial"},
    "title": {"font": {"size": 18, "color": "#ffffff"}},
    "xaxis": {
        "gridcolor": "#2d2d44",
        "linecolor": "#2d2d44",
        "tickfont": {"color": "#aaaaaa"}
    },
    "yaxis": {
        "gridcolor": "#2d2d44",
        "linecolor": "#2d2d44",
        "tickfont": {"color": "#aaaaaa"}
    },
    "legend": {
        "bgcolor": "rgba(0,0,0,0.5)",
        "font": {"color": "#ffffff"}
    }
}

LIGHT_LAYOUT = {
    "paper_bgcolor": "#ffffff",
    "plot_bgcolor": "#ffffff",
    "font": {"color": "#333333", "family": "Segoe UI, Arial"},
    "title": {"font": {"size": 18, "color": "#333333"}},
    "xaxis": {
        "gridcolor": "#e5e5e5",
        "linecolor": "#e5e5e5",
        "tickfont": {"color": "#666666"}
    },
    "yaxis": {
        "gridcolor": "#e5e5e5",
        "linecolor": "#e5e5e5",
        "tickfont": {"color": "#666666"}
    },
    "legend": {
        "bgcolor": "rgba(255,255,255,0.8)",
        "font": {"color": "#333333"}
    }
}

def get_layout(theme: str = "dark") -> dict:
    """Get layout based on theme, only safe properties."""
    is_dark = theme.lower() in ["dark", "amoled"]
    return {
        "paper_bgcolor": "#1a1a2e" if is_dark else "#ffffff",
        "plot_bgcolor": "#1a1a2e" if is_dark else "#ffffff",
        "font": {"color": "#ffffff" if is_dark else "#333333", "family": "Segoe UI, Arial"},
    }

def make_bar_chart(
    title: str,
    categories: List[str],
    values: List[float],
    theme: str = "dark",
    horizontal: bool = False,
    show_values: bool = True
) -> str:
    """
    Create a beautiful bar chart.
    
    Returns:
        HTML string to embed in QWebEngineView
    """
    if not categories or not values:
        return _empty_chart(title, theme)
    
    layout = get_layout(theme)
    
    # Limit to top 10 for readability
    if len(categories) > 10:
        data = list(zip(categories, values))
        data.sort(key=lambda x: x[1], reverse=True)
        categories, values = zip(*data[:10])
        categories, values = list(categories), list(values)
    
    if horizontal:
        fig = go.Figure(data=[
            go.Bar(
                y=categories,
                x=values,
                orientation='h',
                marker=dict(
                    color=values,
                    colorscale='Blues',
                    line=dict(width=0)
                ),
                text=[f"${v:,.0f}" if v > 100 else f"{v:.1f}" for v in values] if show_values else None,
                textposition='auto',
                textfont=dict(color='white', size=12)
            )
        ])
    else:
        fig = go.Figure(data=[
            go.Bar(
                x=categories,
                y=values,
                marker=dict(
                    color=PALETTE[:len(values)],
                    line=dict(width=0)
                ),
                text=[f"${v:,.0f}" if v > 100 else f"{v:.1f}" for v in values] if show_values else None,
                textposition='auto',
                textfont=dict(color='white', size=11)
            )
        ])
    
    fig.update_layout(
        title=dict(text=title, x=0.5),
        margin=dict(l=20, r=20, t=50, b=50),
        showlegend=False,
        **layout
    )
    
    return _fig_to_html(fig)

def make_line_chart(
    title: str,
    labels: List[str],
    values: List[float],
    theme: str = "dark",
    fill: bool = True
) -> str:
    """Create a beautiful line chart with optional area fill."""
    if not labels or not values:
        return _empty_chart(title, theme)
    
    layout = get_layout(theme)
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=labels,
        y=values,
        mode='lines+markers',
        fill='tozeroy' if fill else None,
        fillcolor='rgba(91, 155, 213, 0.3)',
        line=dict(color=COLORS["primary"], width=3, shape='spline'),
        marker=dict(size=8, color=COLORS["primary"], line=dict(width=2, color='white')),
        hovertemplate='%{x}<br>$%{y:,.2f}<extra></extra>'
    ))
    
    fig.update_layout(
        title=dict(text=title, x=0.5),
        margin=dict(l=20, r=20, t=50, b=50),
        showlegend=False,
        hovermode='x unified',
        **layout
    )
    
    return _fig_to_html(fig)

def make_pie_chart(
    title: str,
    labels: List[str],
    values: List[float],
    theme: str = "dark",
    donut: bool = True
) -> str:
    """Create a beautiful pie/donut chart."""
    if not labels or not values:
        return _empty_chart(title, theme)
    
    layout = get_layout(theme)
    
    fig = go.Figure(data=[
        go.Pie(
            labels=labels,
            values=values,
            hole=0.5 if donut else 0,
            marker=dict(colors=PALETTE[:len(values)], line=dict(width=2, color='white')),
            textinfo='percent+label',
            textposition='outside',
            textfont=dict(size=12),
            hovertemplate='%{label}<br>$%{value:,.2f}<br>%{percent}<extra></extra>'
        )
    ])
    
    # Add center text for donut
    if donut:
        total = sum(values)
        fig.add_annotation(
            text=f"<b>${total:,.0f}</b>",
            x=0.5, y=0.5,
            font=dict(size=20, color=layout['font']['color']),
            showarrow=False
        )
    
    fig.update_layout(
        title=dict(text=title, x=0.5),
        margin=dict(l=20, r=20, t=60, b=20),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.2),
        **layout
    )
    
    return _fig_to_html(fig)

def make_kpi_card(
    value: str,
    title: str,
    subtitle: str = "",
    change: Optional[float] = None,
    theme: str = "dark"
) -> str:
    """Create a KPI card with value and optional change indicator."""
    bg_color = "#1a1a2e" if theme.lower() in ["dark", "amoled"] else "#ffffff"
    text_color = "#ffffff" if theme.lower() in ["dark", "amoled"] else "#333333"
    subtitle_color = "#888888"
    
    change_html = ""
    if change is not None:
        arrow = "▲" if change >= 0 else "▼"
        color = "#70AD47" if change >= 0 else "#FF5733"
        change_html = f'<div style="color: {color}; font-size: 14px;">{arrow} {abs(change):.1f}%</div>'
    
    html = f'''
    <div style="
        background: {bg_color};
        border-radius: 10px;
        padding: 20px;
        text-align: center;
        font-family: Segoe UI, Arial;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    ">
        <div style="color: {subtitle_color}; font-size: 12px; text-transform: uppercase; letter-spacing: 1px;">{title}</div>
        <div style="color: {text_color}; font-size: 32px; font-weight: bold; margin: 10px 0;">{value}</div>
        {change_html}
        <div style="color: {subtitle_color}; font-size: 11px;">{subtitle}</div>
    </div>
    '''
    return html

def make_multi_line_chart(
    title: str,
    labels: List[str],
    datasets: Dict[str, List[float]],
    theme: str = "dark"
) -> str:
    """Create a chart with multiple lines/series."""
    if not labels or not datasets:
        return _empty_chart(title, theme)
    
    layout = get_layout(theme)
    fig = go.Figure()
    
    for i, (name, values) in enumerate(datasets.items()):
        fig.add_trace(go.Scatter(
            x=labels,
            y=values,
            mode='lines+markers',
            name=name,
            line=dict(color=PALETTE[i % len(PALETTE)], width=2),
            marker=dict(size=6)
        ))
    
    fig.update_layout(
        title=dict(text=title, x=0.5),
        margin=dict(l=20, r=20, t=50, b=50),
        legend=dict(orientation="h", yanchor="bottom", y=-0.2),
        hovermode='x unified',
        **layout
    )
    
    return _fig_to_html(fig)

def make_gauge_chart(
    value: float,
    title: str,
    max_value: float = 100,
    theme: str = "dark"
) -> str:
    """Create a gauge/speedometer chart."""
    layout = get_layout(theme)
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=value,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': title, 'font': {'size': 16, 'color': layout['font']['color']}},
        number={'font': {'size': 40, 'color': layout['font']['color']}},
        gauge={
            'axis': {'range': [0, max_value], 'tickwidth': 1, 'tickcolor': layout['font']['color']},
            'bar': {'color': COLORS["primary"]},
            'bgcolor': "rgba(255,255,255,0.1)",
            'borderwidth': 0,
            'steps': [
                {'range': [0, max_value * 0.5], 'color': 'rgba(255, 87, 51, 0.3)'},
                {'range': [max_value * 0.5, max_value * 0.75], 'color': 'rgba(255, 192, 0, 0.3)'},
                {'range': [max_value * 0.75, max_value], 'color': 'rgba(112, 173, 71, 0.3)'}
            ],
            'threshold': {
                'line': {'color': "white", 'width': 4},
                'thickness': 0.75,
                'value': value
            }
        }
    ))
    
    fig.update_layout(
        margin=dict(l=30, r=30, t=50, b=10),
        paper_bgcolor=layout['paper_bgcolor'],
        font={'color': layout['font']['color']}
    )
    
    return _fig_to_html(fig)

def _empty_chart(title: str, theme: str = "dark") -> str:
    """Return an empty chart placeholder."""
    layout = get_layout(theme)
    bg = layout['paper_bgcolor']
    color = layout['font']['color']
    
    return f'''
    <div style="
        background: {bg};
        height: 100%;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        font-family: Segoe UI, Arial;
        color: {color};
    ">
        <div style="font-size: 48px; opacity: 0.3;">📊</div>
        <div style="font-size: 16px; margin-top: 10px;">{title}</div>
        <div style="font-size: 12px; opacity: 0.5; margin-top: 5px;">Sin datos disponibles</div>
    </div>
    '''

def _fig_to_html(fig: go.Figure) -> str:
    """Convert Plotly figure to embeddable HTML."""
    config = {
        'displayModeBar': False,
        'responsive': True,
        'scrollZoom': False
    }
    
    html = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
        <style>
            body {{ margin: 0; padding: 0; overflow: hidden; }}
            #chart {{ width: 100%; height: 100vh; }}
        </style>
    </head>
    <body>
        <div id="chart"></div>
        <script>
            var data = {fig.to_json()};
            var config = {json.dumps(config)};
            Plotly.newPlot('chart', data.data, data.layout, config);
            window.addEventListener('resize', function() {{
                Plotly.Plots.resize('chart');
            }});
        </script>
    </body>
    </html>
    '''
    return html

# Aliases for compatibility with existing code
def create_bar_chart(data: dict, title: str, theme: str = "dark") -> str:
    """Compatibility alias."""
    return make_bar_chart(title, list(data.keys()), list(data.values()), theme)

def create_pie_chart(data: dict, title: str, theme: str = "dark") -> str:
    """Compatibility alias."""
    return make_pie_chart(title, list(data.keys()), list(data.values()), theme)
