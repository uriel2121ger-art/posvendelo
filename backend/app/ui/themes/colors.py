"""
TITAN POS - Cyber Night Color Palette
Paleta de colores para el tema Cyber Night (Dark Mode Futurista)
"""


class CyberNight:
    """
    Paleta de colores Cyber Night - Tema oscuro futurista con acentos neón.
    Inspirado en interfaces de 2030, cyberpunk y diseño moderno.
    """
    
    # ============================================================================
    # FONDOS (Backgrounds)
    # ============================================================================
    BG_PRIMARY = "#0B0E14"      # Deep Space - Fondo principal (negro azulado profundo)
    BG_SECONDARY = "#151921"    # Gunmetal - Fondo secundario (gris oscuro)
    BG_TERTIARY = "#1E2530"     # Slate - Fondo terciario (gris medio oscuro)
    BG_CARD = "#1A1F2E"         # Card background (ligeramente más claro)
    BG_HOVER = "#252B3A"        # Hover state (más claro para feedback)
    BG_ACTIVE = "#2A3441"       # Active state (aún más claro)
    
    # ============================================================================
    # ACENTOS PRINCIPALES (Primary Accents)
    # ============================================================================
    ACCENT_PRIMARY = "#00F2FF"   # Cyan Neón - Acento principal (brillante, futurista)
    ACCENT_PRIMARY_HOVER = "#33F5FF"  # Cyan más claro en hover
    ACCENT_PRIMARY_DARK = "#0099A6"   # Cyan oscuro para variaciones
    
    ACCENT_SECONDARY = "#7000FF" # Violeta Neón - Acento secundario
    ACCENT_SECONDARY_HOVER = "#8533FF"  # Violeta más claro en hover
    
    # ============================================================================
    # ESTADOS (Status Colors)
    # ============================================================================
    ACCENT_SUCCESS = "#00FF88"   # Verde Neón - Éxito, confirmación
    ACCENT_SUCCESS_HOVER = "#33FFAA"  # Verde más claro
    ACCENT_SUCCESS_DARK = "#00CC6E"   # Verde oscuro
    
    ACCENT_DANGER = "#FF3366"    # Rosa Neón - Error, peligro, cancelar
    ACCENT_DANGER_HOVER = "#FF6699"   # Rosa más claro
    ACCENT_DANGER_DARK = "#CC1A4D"    # Rosa oscuro
    
    ACCENT_WARNING = "#FFAA00"   # Amarillo Neón - Advertencia
    ACCENT_INFO = "#00D4FF"      # Azul Neón - Información
    
    # ============================================================================
    # TEXTO (Text Colors)
    # ============================================================================
    TEXT_PRIMARY = "#FFFFFF"    # Blanco puro - Texto principal
    TEXT_SECONDARY = "#8B95A5"  # Gris claro - Texto secundario
    TEXT_TERTIARY = "#5A6575"   # Gris medio - Texto terciario (deshabilitado)
    TEXT_DISABLED = "#3A4455"   # Gris oscuro - Texto deshabilitado
    
    # Texto sobre acentos
    TEXT_ON_ACCENT = "#0B0E14"  # Texto oscuro sobre fondos neón
    
    # ============================================================================
    # BORDES (Borders)
    # ============================================================================
    BORDER_DEFAULT = "#2A3441"  # Borde por defecto (gris medio)
    BORDER_FOCUS = "#00F2FF"    # Borde en focus (cyan neón)
    BORDER_HOVER = "#3A4455"    # Borde en hover (gris más claro)
    BORDER_ERROR = "#FF3366"    # Borde de error (rosa neón)
    
    # ============================================================================
    # GRADIENTES (Gradients - para QSS)
    # ============================================================================
    GRADIENT_PRIMARY = (
        "qlineargradient(x1:0, y1:0, x2:1, y2:0, "
        "stop:0 #00F2FF, stop:1 #7000FF)"
    )
    
    GRADIENT_PRIMARY_HOVER = (
        "qlineargradient(x1:0, y1:0, x2:1, y2:0, "
        "stop:0 #33F5FF, stop:1 #8533FF)"
    )
    
    GRADIENT_SUCCESS = (
        "qlineargradient(x1:0, y1:0, x2:1, y2:0, "
        "stop:0 #00FF88, stop:1 #00CC6E)"
    )
    
    GRADIENT_DANGER = (
        "qlineargradient(x1:0, y1:0, x2:1, y2:0, "
        "stop:0 #FF3366, stop:1 #CC1A4D)"
    )
    
    # Gradiente vertical (para cards)
    GRADIENT_CARD = (
        "qlineargradient(x1:0, y1:0, x2:0, y2:1, "
        "stop:0 rgba(30, 37, 48, 0.8), stop:1 rgba(21, 25, 33, 0.9))"
    )
    
    # ============================================================================
    # SOMBRAS (Shadows - para efectos glow)
    # ============================================================================
    SHADOW_PRIMARY = "rgba(0, 242, 255, 0.3)"   # Sombra cyan
    SHADOW_SECONDARY = "rgba(112, 0, 255, 0.3)" # Sombra violeta
    SHADOW_SUCCESS = "rgba(0, 255, 136, 0.3)"   # Sombra verde
    SHADOW_DANGER = "rgba(255, 51, 102, 0.3)"   # Sombra rosa
    
    # ============================================================================
    # DIMENSIONES (Dimensions)
    # ============================================================================
    BORDER_RADIUS_SM = 8    # Border radius pequeño (inputs pequeños)
    BORDER_RADIUS_MD = 12   # Border radius medio (botones, cards)
    BORDER_RADIUS_LG = 16   # Border radius grande (diálogos, paneles)
    BORDER_RADIUS_XL = 24   # Border radius extra grande (modales)
    
    # ============================================================================
    # ESPACIADO (Spacing)
    # ============================================================================
    SPACING_XS = 4
    SPACING_SM = 8
    SPACING_MD = 16
    SPACING_LG = 24
    SPACING_XL = 32
    
    # ============================================================================
    # FUENTES (Fonts)
    # ============================================================================
    FONT_FAMILY_UI = "Inter"              # Fuente principal UI
    FONT_FAMILY_MONO = "JetBrains Mono"  # Fuente monoespaciada (precios, SKUs)
    
    FONT_SIZE_XS = 10
    FONT_SIZE_SM = 12
    FONT_SIZE_MD = 14
    FONT_SIZE_LG = 16
    FONT_SIZE_XL = 18
    FONT_SIZE_XXL = 24
    FONT_SIZE_XXXL = 32
    
    # ============================================================================
    # ANIMACIONES (Animation Durations)
    # ============================================================================
    ANIMATION_FAST = 150      # Animación rápida (ms)
    ANIMATION_NORMAL = 300    # Animación normal (ms)
    ANIMATION_SLOW = 500      # Animación lenta (ms)
    
    # ============================================================================
    # OPACIDADES (Opacities - para glassmorphism)
    # ============================================================================
    OPACITY_GLASS = 0.1       # Opacidad para efecto glass
    OPACITY_HOVER = 0.15      # Opacidad en hover
    OPACITY_ACTIVE = 0.2      # Opacidad en estado activo
    OPACITY_DISABLED = 0.3    # Opacidad para elementos deshabilitados
    
    # ============================================================================
    # MÉTODOS HELPER
    # ============================================================================
    
    @classmethod
    def get_color_dict(cls) -> dict:
        """
        Retorna un diccionario con todos los colores.
        Útil para pasar a funciones que necesitan colores.
        """
        return {
            'bg_primary': cls.BG_PRIMARY,
            'bg_secondary': cls.BG_SECONDARY,
            'bg_tertiary': cls.BG_TERTIARY,
            'bg_card': cls.BG_CARD,
            'bg_hover': cls.BG_HOVER,
            'bg_active': cls.BG_ACTIVE,
            'accent_primary': cls.ACCENT_PRIMARY,
            'accent_secondary': cls.ACCENT_SECONDARY,
            'accent_success': cls.ACCENT_SUCCESS,
            'accent_danger': cls.ACCENT_DANGER,
            'accent_warning': cls.ACCENT_WARNING,
            'accent_info': cls.ACCENT_INFO,
            'text_primary': cls.TEXT_PRIMARY,
            'text_secondary': cls.TEXT_SECONDARY,
            'text_tertiary': cls.TEXT_TERTIARY,
            'text_disabled': cls.TEXT_DISABLED,
            'border_default': cls.BORDER_DEFAULT,
            'border_focus': cls.BORDER_FOCUS,
            'border_hover': cls.BORDER_HOVER,
            'border_error': cls.BORDER_ERROR,
        }
    
    @classmethod
    def get_gradient(cls, variant: str = "primary") -> str:
        """
        Retorna un gradiente según la variante.
        
        Args:
            variant: "primary", "success", "danger"
        """
        gradients = {
            "primary": cls.GRADIENT_PRIMARY,
            "primary_hover": cls.GRADIENT_PRIMARY_HOVER,
            "success": cls.GRADIENT_SUCCESS,
            "danger": cls.GRADIENT_DANGER,
        }
        return gradients.get(variant, cls.GRADIENT_PRIMARY)
