"""
Charts Matplotlib - Gráficos modernos con Matplotlib + Qt
Diseño premium compatible con ThemeManager de TITAN POS
"""

from typing import Any, Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# Intentar importar matplotlib
try:
    import matplotlib
    matplotlib.use('QtAgg')  # Backend Qt
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.colors import LinearSegmentedColormap
    from matplotlib.figure import Figure
    import matplotlib.patches as mpatches
    import matplotlib.pyplot as plt
    import numpy as np
    HAS_MATPLOTLIB = True
except ImportError as e:
    logger.warning(f"Matplotlib no disponible: {e}")
    HAS_MATPLOTLIB = False
    FigureCanvas = None
    Figure = None

# ═══════════════════════════════════════════════════════════════════════════════
# PALETA DE COLORES TITAN (sincronizada con ThemeManager)
# ═══════════════════════════════════════════════════════════════════════════════

# Colores por defecto (Dark theme)
TITAN_COLORS = {
    # Fondos
    "bg_dark": "#1a1d23",
    "bg_card": "#2a2f38",
    "bg_hover": "#3a3f48",
    
    # Texto
    "text_primary": "#e8eaed",
    "text_secondary": "#a0a4ab",
    "text_muted": "#6c7280",
    
    # Acentos
    "accent": "#00C896",
    "accent_light": "#00E0A8",
    "accent_dark": "#00a07a",
    
    # Colores para series de datos
    "series": [
        "#00C896",  # Verde TITAN (primario)
        "#3498db",  # Azul
        "#9b59b6",  # Púrpura
        "#e74c3c",  # Rojo
        "#f39c12",  # Naranja
        "#1abc9c",  # Turquesa
        "#e91e63",  # Rosa
        "#00bcd4",  # Cyan
    ],
    
    # Gradientes para barras
    "gradient_start": "#00C896",
    "gradient_end": "#00a07a",
    
    # Bordes
    "border": "#3a3f48",
    "grid": "#2a2f38",
}

def sync_with_theme_manager(theme_name: str = None) -> dict:
    """
    Sincroniza los colores de las gráficas con el ThemeManager de TITAN.
    
    Args:
        theme_name: Nombre del tema ('Dark', 'Gray', 'AMOLED', 'Light').
                   Si es None, intenta obtenerlo de la configuración.
    
    Returns:
        Diccionario con los colores actualizados.
    """
    # Intentar obtener tema de la configuración
    if theme_name is None:
        try:
            from app.utils.theme_manager import theme_manager
            theme_name = theme_manager.current_theme
        except ImportError:
            theme_name = "Dark"
    
    # Obtener colores del ThemeManager
    try:
        from app.utils.theme_manager import theme_manager
        colors = theme_manager.get_colors(theme_name)
        
        # Mapear colores del ThemeManager a TITAN_COLORS
        TITAN_COLORS.update({
            "bg_dark": colors.get("bg_main", TITAN_COLORS["bg_dark"]),
            "bg_card": colors.get("bg_card", TITAN_COLORS["bg_card"]),
            "bg_hover": colors.get("border_light", colors.get("border", TITAN_COLORS["bg_hover"])),
            "text_primary": colors.get("text_primary", TITAN_COLORS["text_primary"]),
            "text_secondary": colors.get("text_secondary", TITAN_COLORS["text_secondary"]),
            "text_muted": colors.get("text_muted", colors.get("text_disabled", TITAN_COLORS["text_muted"])),
            "accent": colors.get("accent", TITAN_COLORS["accent"]),
            "accent_light": colors.get("accent_hover", TITAN_COLORS["accent_light"]),
            "accent_dark": colors.get("accent_dark", TITAN_COLORS["accent_dark"]),
            "border": colors.get("border", TITAN_COLORS["border"]),
            "grid": colors.get("bg_secondary", TITAN_COLORS["grid"]),
            "gradient_start": colors.get("accent", TITAN_COLORS["gradient_start"]),
            "gradient_end": colors.get("accent_dark", TITAN_COLORS["gradient_end"]),
        })
        
        # Actualizar matplotlib rcParams
        if HAS_MATPLOTLIB:
            _apply_titan_style()
        
        logger.debug(f"Charts sincronizados con tema: {theme_name}")
    except Exception as e:
        logger.warning(f"No se pudo sincronizar con ThemeManager: {e}")
    
    return TITAN_COLORS

def get_theme_colors() -> dict:
    """Obtiene los colores actuales de las gráficas."""
    return TITAN_COLORS.copy()

def _apply_titan_style():
    """Aplica el estilo TITAN a matplotlib globalmente."""
    if not HAS_MATPLOTLIB:
        return
    
    plt.style.use('dark_background')
    
    # Configuración global
    plt.rcParams.update({
        # Fondo
        'figure.facecolor': TITAN_COLORS["bg_dark"],
        'axes.facecolor': TITAN_COLORS["bg_card"],
        'savefig.facecolor': TITAN_COLORS["bg_dark"],
        
        # Texto
        'text.color': TITAN_COLORS["text_primary"],
        'axes.labelcolor': TITAN_COLORS["text_primary"],
        'xtick.color': TITAN_COLORS["text_secondary"],
        'ytick.color': TITAN_COLORS["text_secondary"],
        
        # Grid
        'axes.grid': True,
        'grid.color': TITAN_COLORS["grid"],
        'grid.alpha': 0.3,
        'grid.linestyle': '--',
        
        # Bordes
        'axes.edgecolor': TITAN_COLORS["border"],
        'axes.linewidth': 1,
        
        # Fuentes
        'font.family': ['Segoe UI', 'SF Pro Display', 'Roboto', 'sans-serif'],
        'font.size': 11,
        'axes.titlesize': 14,
        'axes.titleweight': 'bold',
        'axes.labelsize': 11,
        
        # Leyenda
        'legend.facecolor': TITAN_COLORS["bg_card"],
        'legend.edgecolor': TITAN_COLORS["border"],
        'legend.fontsize': 10,
        
        # Spines (bordes del gráfico)
        'axes.spines.top': False,
        'axes.spines.right': False,
    })

# Aplicar estilo al importar
_apply_titan_style()

# ═══════════════════════════════════════════════════════════════════════════════
# CLASE BASE PARA CANVAS
# ═══════════════════════════════════════════════════════════════════════════════

class TitanChartCanvas(FigureCanvas if HAS_MATPLOTLIB else object):
    """Canvas base para gráficos TITAN con estilo premium."""
    
    def __init__(self, width: int = 8, height: int = 5, dpi: int = 100):
        if not HAS_MATPLOTLIB:
            raise ImportError("Matplotlib no está disponible")
        
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.fig.patch.set_facecolor(TITAN_COLORS["bg_dark"])
        
        super().__init__(self.fig)
        
        self.axes = self.fig.add_subplot(111)
        self._style_axes(self.axes)
    
    def _style_axes(self, ax):
        """Aplica estilo TITAN a un eje."""
        ax.set_facecolor(TITAN_COLORS["bg_card"])
        ax.tick_params(colors=TITAN_COLORS["text_secondary"])
        ax.xaxis.label.set_color(TITAN_COLORS["text_primary"])
        ax.yaxis.label.set_color(TITAN_COLORS["text_primary"])
        ax.title.set_color(TITAN_COLORS["accent"])
        
        # Bordes redondeados simulados con patch
        for spine in ax.spines.values():
            spine.set_color(TITAN_COLORS["border"])
            spine.set_linewidth(1.5)
    
    def clear(self):
        """Limpia el canvas."""
        self.axes.clear()
        self._style_axes(self.axes)
        self.draw()

# ═══════════════════════════════════════════════════════════════════════════════
# GRÁFICO DE BARRAS PREMIUM
# ═══════════════════════════════════════════════════════════════════════════════

class BarChartCanvas(TitanChartCanvas):
    """Gráfico de barras con gradientes y animaciones."""
    
    def __init__(self, width: int = 8, height: int = 5, dpi: int = 100):
        super().__init__(width, height, dpi)
    
    def plot(self, categories: List[str], values: List[float], 
             title: str = "", ylabel: str = "Valor",
             horizontal: bool = False, show_values: bool = True,
             color: str = None):
        """
        Dibuja un gráfico de barras premium.
        
        Args:
            categories: Lista de categorías (eje X o Y)
            values: Lista de valores numéricos
            title: Título del gráfico
            ylabel: Etiqueta del eje Y
            horizontal: Si True, barras horizontales
            show_values: Si True, muestra valores sobre las barras
            color: Color personalizado (usa gradiente TITAN si None)
        """
        self.axes.clear()
        self._style_axes(self.axes)
        
        if not categories or not values:
            self.axes.text(0.5, 0.5, "Sin datos", ha='center', va='center',
                          color=TITAN_COLORS["text_muted"], fontsize=14)
            self.draw()
            return
        
        x = np.arange(len(categories))
        values_arr = np.array([float(v) if v else 0 for v in values])
        
        # Color con gradiente
        if color is None:
            # Crear gradiente de colores basado en valores
            norm_values = values_arr / (max(values_arr) if max(values_arr) > 0 else 1)
            colors = [self._interpolate_color(
                TITAN_COLORS["accent_dark"], 
                TITAN_COLORS["accent_light"], 
                v
            ) for v in norm_values]
        else:
            colors = [color] * len(values)
        
        if horizontal:
            bars = self.axes.barh(x, values_arr, color=colors, 
                                  edgecolor=TITAN_COLORS["border"], linewidth=0.5,
                                  height=0.6)
            self.axes.set_yticks(x)
            self.axes.set_yticklabels([self._truncate(c, 20) for c in categories])
            self.axes.set_xlabel(ylabel)
            self.axes.invert_yaxis()
            
            if show_values:
                for bar, val in zip(bars, values_arr):
                    self.axes.text(bar.get_width() + max(values_arr) * 0.02, 
                                  bar.get_y() + bar.get_height()/2,
                                  f"${val:,.0f}" if val >= 100 else f"{val:,.2f}",
                                  va='center', ha='left',
                                  color=TITAN_COLORS["text_primary"],
                                  fontsize=9, fontweight='bold')
        else:
            bars = self.axes.bar(x, values_arr, color=colors,
                                edgecolor=TITAN_COLORS["border"], linewidth=0.5,
                                width=0.6)
            self.axes.set_xticks(x)
            self.axes.set_xticklabels([self._truncate(c, 10) for c in categories], 
                                       rotation=45, ha='right')
            self.axes.set_ylabel(ylabel)
            
            if show_values:
                for bar, val in zip(bars, values_arr):
                    height = bar.get_height()
                    self.axes.text(bar.get_x() + bar.get_width()/2, height + max(values_arr) * 0.02,
                                  f"${val:,.0f}" if val >= 100 else f"{val:,.2f}",
                                  ha='center', va='bottom',
                                  color=TITAN_COLORS["text_primary"],
                                  fontsize=9, fontweight='bold')
        
        if title:
            self.axes.set_title(title, pad=15, color=TITAN_COLORS["accent"])
        
        self.fig.tight_layout()
        self.draw()
    
    def _interpolate_color(self, color1: str, color2: str, factor: float) -> str:
        """Interpola entre dos colores hex."""
        c1 = tuple(int(color1.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
        c2 = tuple(int(color2.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
        result = tuple(int(c1[i] + (c2[i] - c1[i]) * factor) for i in range(3))
        return f"#{result[0]:02x}{result[1]:02x}{result[2]:02x}"
    
    def _truncate(self, text: str, max_len: int) -> str:
        """Trunca texto largo."""
        text = str(text)
        return text[:max_len-2] + "…" if len(text) > max_len else text

# ═══════════════════════════════════════════════════════════════════════════════
# GRÁFICO DE LÍNEAS PREMIUM
# ═══════════════════════════════════════════════════════════════════════════════

class LineChartCanvas(TitanChartCanvas):
    """Gráfico de líneas con área sombreada y marcadores."""
    
    def __init__(self, width: int = 8, height: int = 5, dpi: int = 100):
        super().__init__(width, height, dpi)
    
    def plot(self, labels: List[str], values: List[float],
             title: str = "", ylabel: str = "Valor",
             fill: bool = True, markers: bool = True,
             smooth: bool = True, color: str = None):
        """
        Dibuja un gráfico de líneas premium.
        
        Args:
            labels: Etiquetas del eje X
            values: Valores numéricos
            title: Título del gráfico
            ylabel: Etiqueta del eje Y
            fill: Si True, rellena el área bajo la curva
            markers: Si True, muestra marcadores en puntos de datos
            smooth: Si True, suaviza la línea (requiere más de 3 puntos)
            color: Color personalizado
        """
        self.axes.clear()
        self._style_axes(self.axes)
        
        if not labels or not values:
            self.axes.text(0.5, 0.5, "Sin datos", ha='center', va='center',
                          color=TITAN_COLORS["text_muted"], fontsize=14)
            self.draw()
            return
        
        x = np.arange(len(labels))
        y = np.array([float(v) if v else 0 for v in values])
        
        line_color = color or TITAN_COLORS["accent"]
        
        # Línea principal
        if smooth and len(x) > 3:
            try:
                from scipy.interpolate import make_interp_spline
                x_smooth = np.linspace(x.min(), x.max(), 200)
                spl = make_interp_spline(x, y, k=min(3, len(x)-1))
                y_smooth = spl(x_smooth)
                self.axes.plot(x_smooth, y_smooth, color=line_color, linewidth=2.5)
                
                if fill:
                    self.axes.fill_between(x_smooth, y_smooth, alpha=0.2, color=line_color)
            except ImportError:
                # Fallback sin scipy
                self.axes.plot(x, y, color=line_color, linewidth=2.5)
                if fill:
                    self.axes.fill_between(x, y, alpha=0.2, color=line_color)
        else:
            self.axes.plot(x, y, color=line_color, linewidth=2.5)
            if fill:
                self.axes.fill_between(x, y, alpha=0.2, color=line_color)
        
        # Marcadores
        if markers:
            self.axes.scatter(x, y, color=line_color, s=50, zorder=5,
                             edgecolors=TITAN_COLORS["bg_dark"], linewidths=2)
        
        self.axes.set_xticks(x)
        self.axes.set_xticklabels([str(l)[:10] for l in labels], rotation=45, ha='right')
        self.axes.set_ylabel(ylabel)
        
        if title:
            self.axes.set_title(title, pad=15, color=TITAN_COLORS["accent"])
        
        # Límites con padding
        y_min, y_max = min(y), max(y)
        padding = (y_max - y_min) * 0.1 or 10
        self.axes.set_ylim(max(0, y_min - padding), y_max + padding)
        
        self.fig.tight_layout()
        self.draw()
    
    def plot_multi(self, labels: List[str], series: Dict[str, List[float]],
                   title: str = "", ylabel: str = "Valor"):
        """
        Dibuja múltiples series de líneas.
        
        Args:
            labels: Etiquetas del eje X
            series: Diccionario {nombre_serie: valores}
            title: Título del gráfico
            ylabel: Etiqueta del eje Y
        """
        self.axes.clear()
        self._style_axes(self.axes)
        
        if not labels or not series:
            self.axes.text(0.5, 0.5, "Sin datos", ha='center', va='center',
                          color=TITAN_COLORS["text_muted"], fontsize=14)
            self.draw()
            return
        
        x = np.arange(len(labels))
        colors = TITAN_COLORS["series"]
        
        for i, (name, values) in enumerate(series.items()):
            y = np.array([float(v) if v else 0 for v in values])
            color = colors[i % len(colors)]
            self.axes.plot(x, y, color=color, linewidth=2.5, label=name, marker='o', markersize=5)
        
        self.axes.set_xticks(x)
        self.axes.set_xticklabels([str(l)[:10] for l in labels], rotation=45, ha='right')
        self.axes.set_ylabel(ylabel)
        
        if title:
            self.axes.set_title(title, pad=15, color=TITAN_COLORS["accent"])
        
        self.axes.legend(loc='upper right')
        self.fig.tight_layout()
        self.draw()

# ═══════════════════════════════════════════════════════════════════════════════
# GRÁFICO DE PASTEL PREMIUM
# ═══════════════════════════════════════════════════════════════════════════════

class PieChartCanvas(TitanChartCanvas):
    """Gráfico de pastel/dona con estilo moderno."""
    
    def __init__(self, width: int = 6, height: int = 6, dpi: int = 100):
        super().__init__(width, height, dpi)
    
    def plot(self, labels: List[str], values: List[float],
             title: str = "", donut: bool = True,
             show_percentages: bool = True):
        """
        Dibuja un gráfico de pastel/dona premium.
        
        Args:
            labels: Etiquetas de las secciones
            values: Valores numéricos
            title: Título del gráfico
            donut: Si True, dibuja como dona (hueco en el centro)
            show_percentages: Si True, muestra porcentajes
        """
        self.axes.clear()
        self._style_axes(self.axes)
        
        if not labels or not values:
            self.axes.text(0.5, 0.5, "Sin datos", ha='center', va='center',
                          color=TITAN_COLORS["text_muted"], fontsize=14)
            self.draw()
            return
        
        values_arr = np.array([float(v) if v and float(v) > 0 else 0.001 for v in values])
        colors = TITAN_COLORS["series"][:len(values)]
        
        # Explotar ligeramente el segmento más grande
        explode = [0.02] * len(values)
        max_idx = np.argmax(values_arr)
        explode[max_idx] = 0.08
        
        wedges, texts, autotexts = self.axes.pie(
            values_arr,
            labels=None,  # Las ponemos en la leyenda
            autopct='%1.1f%%' if show_percentages else '',
            colors=colors,
            explode=explode,
            startangle=90,
            wedgeprops={'edgecolor': TITAN_COLORS["bg_dark"], 'linewidth': 2},
            pctdistance=0.75 if donut else 0.6,
        )
        
        # Estilo de porcentajes
        for autotext in autotexts:
            autotext.set_color(TITAN_COLORS["text_primary"])
            autotext.set_fontsize(10)
            autotext.set_fontweight('bold')
        
        # Dona (hueco central)
        if donut:
            center_circle = plt.Circle((0, 0), 0.5, fc=TITAN_COLORS["bg_card"],
                                       ec=TITAN_COLORS["border"], linewidth=2)
            self.axes.add_patch(center_circle)
            
            # Texto central con total
            total = sum(values_arr)
            self.axes.text(0, 0, f"${total:,.0f}", ha='center', va='center',
                          fontsize=16, fontweight='bold',
                          color=TITAN_COLORS["accent"])
        
        # Leyenda
        legend_labels = [f"{l}: ${v:,.0f}" for l, v in zip(labels, values_arr)]
        self.axes.legend(wedges, legend_labels, loc='center left',
                        bbox_to_anchor=(1, 0.5), fontsize=9)
        
        if title:
            self.axes.set_title(title, pad=15, color=TITAN_COLORS["accent"], fontsize=14)
        
        self.axes.set_aspect('equal')
        self.fig.tight_layout()
        self.draw()

# ═══════════════════════════════════════════════════════════════════════════════
# GRÁFICO DE ÁREA APILADO
# ═══════════════════════════════════════════════════════════════════════════════

class StackedAreaCanvas(TitanChartCanvas):
    """Gráfico de área apilado para comparar categorías en el tiempo."""
    
    def __init__(self, width: int = 10, height: int = 5, dpi: int = 100):
        super().__init__(width, height, dpi)
    
    def plot(self, labels: List[str], series: Dict[str, List[float]],
             title: str = "", ylabel: str = "Valor"):
        """
        Dibuja un gráfico de área apilado.
        
        Args:
            labels: Etiquetas del eje X (tiempo)
            series: Diccionario {nombre_serie: valores}
            title: Título del gráfico
            ylabel: Etiqueta del eje Y
        """
        self.axes.clear()
        self._style_axes(self.axes)
        
        if not labels or not series:
            self.axes.text(0.5, 0.5, "Sin datos", ha='center', va='center',
                          color=TITAN_COLORS["text_muted"], fontsize=14)
            self.draw()
            return
        
        x = np.arange(len(labels))
        y_data = []
        names = []
        colors = TITAN_COLORS["series"][:len(series)]
        
        for name, values in series.items():
            y = np.array([float(v) if v else 0 for v in values])
            y_data.append(y)
            names.append(name)
        
        self.axes.stackplot(x, *y_data, labels=names, colors=colors, alpha=0.8,
                           edgecolor=TITAN_COLORS["bg_dark"], linewidth=1)
        
        self.axes.set_xticks(x)
        self.axes.set_xticklabels([str(l)[:10] for l in labels], rotation=45, ha='right')
        self.axes.set_ylabel(ylabel)
        
        if title:
            self.axes.set_title(title, pad=15, color=TITAN_COLORS["accent"])
        
        self.axes.legend(loc='upper left')
        self.fig.tight_layout()
        self.draw()

# ═══════════════════════════════════════════════════════════════════════════════
# FUNCIONES DE COMPATIBILIDAD (API similar a charts_helper.py)
# ═══════════════════════════════════════════════════════════════════════════════

def create_bar_chart_widget(categories: List[str], values: List[float],
                            title: str = "", **kwargs) -> Optional[FigureCanvas]:
    """Crea un widget de gráfico de barras listo para insertar en Qt."""
    if not HAS_MATPLOTLIB:
        logger.warning("Matplotlib no disponible para crear gráfico de barras")
        return None
    
    canvas = BarChartCanvas()
    canvas.plot(categories, values, title, **kwargs)
    return canvas

def create_line_chart_widget(labels: List[str], values: List[float],
                             title: str = "", **kwargs) -> Optional[FigureCanvas]:
    """Crea un widget de gráfico de líneas listo para insertar en Qt."""
    if not HAS_MATPLOTLIB:
        logger.warning("Matplotlib no disponible para crear gráfico de líneas")
        return None
    
    canvas = LineChartCanvas()
    canvas.plot(labels, values, title, **kwargs)
    return canvas

def create_pie_chart_widget(labels: List[str], values: List[float],
                            title: str = "", **kwargs) -> Optional[FigureCanvas]:
    """Crea un widget de gráfico de pastel listo para insertar en Qt."""
    if not HAS_MATPLOTLIB:
        logger.warning("Matplotlib no disponible para crear gráfico de pastel")
        return None
    
    canvas = PieChartCanvas()
    canvas.plot(labels, values, title, **kwargs)
    return canvas

# Alias para compatibilidad con charts_helper.py existente
def make_line_chart(title: str, labels: list, values: list):
    """Alias compatible con charts_helper.make_line_chart."""
    return create_line_chart_widget(labels, values, title)

def make_bar_chart(title: str, categories: list, values: list):
    """Alias compatible con charts_helper.make_bar_chart."""
    return create_bar_chart_widget(categories, values, title)

def make_pie_chart(title: str, labels: list, values: list):
    """Alias compatible con charts_helper.make_pie_chart."""
    return create_pie_chart_widget(labels, values, title)

# ═══════════════════════════════════════════════════════════════════════════════
# DASHBOARD WIDGET (múltiples gráficos en grid)
# ═══════════════════════════════════════════════════════════════════════════════

class DashboardCanvas(FigureCanvas if HAS_MATPLOTLIB else object):
    """Canvas con múltiples gráficos organizados en grid."""
    
    def __init__(self, rows: int = 2, cols: int = 2, 
                 width: int = 12, height: int = 8, dpi: int = 100):
        if not HAS_MATPLOTLIB:
            raise ImportError("Matplotlib no está disponible")
        
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.fig.patch.set_facecolor(TITAN_COLORS["bg_dark"])
        
        super().__init__(self.fig)
        
        self.rows = rows
        self.cols = cols
        self.axes_list = []
        
        for i in range(rows * cols):
            ax = self.fig.add_subplot(rows, cols, i + 1)
            self._style_axes(ax)
            self.axes_list.append(ax)
        
        self.fig.tight_layout(pad=3.0)
    
    def _style_axes(self, ax):
        """Aplica estilo TITAN a un eje."""
        ax.set_facecolor(TITAN_COLORS["bg_card"])
        ax.tick_params(colors=TITAN_COLORS["text_secondary"], labelsize=9)
        ax.xaxis.label.set_color(TITAN_COLORS["text_primary"])
        ax.yaxis.label.set_color(TITAN_COLORS["text_primary"])
        ax.title.set_color(TITAN_COLORS["accent"])
        
        for spine in ax.spines.values():
            spine.set_color(TITAN_COLORS["border"])
            spine.set_linewidth(1)
        
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
    
    def get_axes(self, index: int):
        """Obtiene un eje específico para dibujar."""
        if 0 <= index < len(self.axes_list):
            return self.axes_list[index]
        return None
    
    def refresh(self):
        """Refresca el canvas después de dibujar."""
        self.fig.tight_layout(pad=2.0)
        self.draw()

# ═══════════════════════════════════════════════════════════════════════════════
# TEST / DEMO
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    """Demo de los gráficos."""
    import sys

    from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget, QVBoxLayout, QWidget
    
    app = QApplication(sys.argv)
    
    window = QMainWindow()
    window.setWindowTitle("TITAN Charts Demo")
    window.setMinimumSize(900, 700)
    window.setStyleSheet(f"background: {TITAN_COLORS['bg_dark']};")
    
    tabs = QTabWidget()
    
    # Demo datos
    categories = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    values = [12500, 15800, 13200, 18400, 22100, 28500, 19200]
    
    # Tab 1: Barras
    bar_canvas = BarChartCanvas()
    bar_canvas.plot(categories, values, "Ventas por Día", ylabel="$MXN")
    tabs.addTab(bar_canvas, "📊 Barras")
    
    # Tab 2: Líneas
    line_canvas = LineChartCanvas()
    line_canvas.plot(categories, values, "Tendencia de Ventas", fill=True)
    tabs.addTab(line_canvas, "📈 Líneas")
    
    # Tab 3: Pastel
    pie_categories = ["Efectivo", "Tarjeta", "Transferencia", "Crédito"]
    pie_values = [45000, 32000, 18000, 5000]
    pie_canvas = PieChartCanvas()
    pie_canvas.plot(pie_categories, pie_values, "Métodos de Pago", donut=True)
    tabs.addTab(pie_canvas, "🥧 Pastel")
    
    # Tab 4: Dashboard
    dashboard = DashboardCanvas(2, 2)
    ax1 = dashboard.get_axes(0)
    ax1.bar(range(len(categories)), values, color=TITAN_COLORS["accent"])
    ax1.set_title("Ventas Semanales")
    
    ax2 = dashboard.get_axes(1)
    ax2.plot(range(len(categories)), values, color=TITAN_COLORS["accent"], marker='o')
    ax2.fill_between(range(len(categories)), values, alpha=0.2, color=TITAN_COLORS["accent"])
    ax2.set_title("Tendencia")
    
    ax3 = dashboard.get_axes(2)
    ax3.pie(pie_values, colors=TITAN_COLORS["series"][:4], autopct='%1.0f%%',
           wedgeprops={'edgecolor': TITAN_COLORS["bg_dark"]})
    ax3.set_title("Por Método")
    
    ax4 = dashboard.get_axes(3)
    ax4.barh(range(4), pie_values, color=TITAN_COLORS["series"][:4])
    ax4.set_yticks(range(4))
    ax4.set_yticklabels(pie_categories)
    ax4.set_title("Comparativo")
    
    dashboard.refresh()
    tabs.addTab(dashboard, "📋 Dashboard")
    
    window.setCentralWidget(tabs)
    window.show()
    
    sys.exit(app.exec())
