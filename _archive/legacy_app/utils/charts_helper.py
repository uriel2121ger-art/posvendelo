"""
Charts Helper - Funciones para crear gráficos con PyQt6 Charts
"""

try:
    from PyQt6 import QtCharts
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QColor, QPainter
    HAS_CHARTS = True
except ImportError:
    HAS_CHARTS = False

def make_line_chart(title: str, labels: list, values: list):
    """Crea un gráfico de líneas."""
    if not HAS_CHARTS or not labels or not values:
        return QtCharts.QChart() if HAS_CHARTS else None
    
    chart = QtCharts.QChart()
    chart.setTitle(title)
    chart.setAnimationOptions(QtCharts.QChart.AnimationOption.SeriesAnimations)
    
    series = QtCharts.QLineSeries()
    for i, value in enumerate(values):
        series.append(i, float(value) if value else 0)
    
    chart.addSeries(series)
    
    # Eje X
    axis_x = QtCharts.QCategoryAxis()
    for i, label in enumerate(labels):
        axis_x.append(str(label)[:10], i)
    chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
    series.attachAxis(axis_x)
    
    # Eje Y
    axis_y = QtCharts.QValueAxis()
    max_val = max(values) if values else 100
    axis_y.setRange(0, float(max_val) * 1.1)
    chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
    series.attachAxis(axis_y)
    
    chart.legend().hide()
    return chart

def make_bar_chart(title: str, categories: list, values: list):
    """Crea un gráfico de barras."""
    if not HAS_CHARTS or not categories or not values:
        return QtCharts.QChart() if HAS_CHARTS else None
    
    chart = QtCharts.QChart()
    chart.setTitle(title)
    chart.setAnimationOptions(QtCharts.QChart.AnimationOption.SeriesAnimations)
    
    series = QtCharts.QBarSeries()
    bar_set = QtCharts.QBarSet("Valores")
    
    for value in values:
        bar_set.append(float(value) if value else 0)
    
    series.append(bar_set)
    chart.addSeries(series)
    
    # Eje X
    axis_x = QtCharts.QBarCategoryAxis()
    axis_x.append([str(c)[:15] for c in categories])
    chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
    series.attachAxis(axis_x)
    
    # Eje Y
    axis_y = QtCharts.QValueAxis()
    max_val = max(values) if values else 100
    axis_y.setRange(0, float(max_val) * 1.1)
    chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
    series.attachAxis(axis_y)
    
    chart.legend().hide()
    return chart

def make_pie_chart(title: str, labels: list, values: list):
    """Crea un gráfico de pastel."""
    if not HAS_CHARTS or not labels or not values:
        return QtCharts.QChart() if HAS_CHARTS else None
    
    chart = QtCharts.QChart()
    chart.setTitle(title)
    chart.setAnimationOptions(QtCharts.QChart.AnimationOption.SeriesAnimations)
    
    series = QtCharts.QPieSeries()
    
    for label, value in zip(labels, values):
        slice_ = series.append(str(label), float(value) if value else 0)
        slice_.setLabelVisible(True)
    
    chart.addSeries(series)
    chart.legend().setAlignment(Qt.AlignmentFlag.AlignRight)
    
    return chart

# Alias para compatibilidad
def create_bar_chart(data, title):
    """Alias para make_bar_chart."""
    if isinstance(data, dict):
        return make_bar_chart(title, list(data.keys()), list(data.values()))
    return None

def create_pie_chart(data, title):
    """Alias para make_pie_chart."""
    if isinstance(data, dict):
        return make_pie_chart(title, list(data.keys()), list(data.values()))
    return None
