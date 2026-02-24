"""
TITAN POS - Theme Loader
Carga y aplica temas QSS a la aplicación.
"""

import logging
from pathlib import Path
from typing import Optional

from PyQt6 import QtWidgets, QtGui

# FIX 2026-02-01: Import agent_log_enabled ANTES de usarla
try:
    from app.utils.path_utils import agent_log_enabled
except ImportError:
    def agent_log_enabled(): return False

logger = logging.getLogger(__name__)


def get_theme_path(theme_name: str) -> Optional[Path]:
    """
    Obtiene la ruta al archivo QSS del tema.
    
    Args:
        theme_name: Nombre del tema (ej: "cyber_night")
    
    Returns:
        Path al archivo QSS o None si no existe
    """
    # Buscar en app/ui/themes/
    theme_dir = Path(__file__).parent
    qss_file = theme_dir / f"{theme_name}.qss"
    
    if qss_file.exists():
        return qss_file
    
    # Buscar en assets/themes/ (alternativa)
    assets_dir = theme_dir.parent / "assets" / "themes"
    qss_file = assets_dir / f"{theme_name}.qss"
    
    if qss_file.exists():
        return qss_file
    
    logger.warning(f"Tema '{theme_name}' no encontrado en {theme_dir} ni {assets_dir}")
    return None


def load_theme(app: QtWidgets.QApplication, theme_name: str) -> bool:
    """
    Carga y aplica un tema QSS a la aplicación.
    
    Args:
        app: Instancia de QApplication
        theme_name: Nombre del tema (ej: "cyber_night")
    
    Returns:
        True si el tema se cargó correctamente, False en caso contrario
    """
    qss_path = get_theme_path(theme_name)
    
    if not qss_path:
        logger.error(f"No se pudo encontrar el tema '{theme_name}'")
        return False
    
    try:
        with open(qss_path, 'r', encoding='utf-8') as f:
            qss_content = f.read()
        
        # Aplicar estilos
        app.setStyleSheet(qss_content)
        
        logger.info(f"✅ Tema '{theme_name}' cargado desde {qss_path}")
        return True
    
    except Exception as e:
        logger.error(f"Error cargando tema '{theme_name}': {e}")
        return False


def load_fonts(app: QtWidgets.QApplication, fonts_dir: Optional[Path] = None) -> bool:
    """
    Carga fuentes personalizadas desde el directorio especificado.
    
    Args:
        app: Instancia de QApplication
        fonts_dir: Directorio con fuentes (por defecto: app/ui/assets/fonts/)
    
    Returns:
        True si se cargaron fuentes, False en caso contrario
    """
    if fonts_dir is None:
        fonts_dir = Path(__file__).parent.parent / "assets" / "fonts"
    
    if not fonts_dir.exists():
        logger.warning(f"Directorio de fuentes no existe: {fonts_dir}")
        return False
    
    from PyQt6 import QtGui
    
    # CRITICAL FIX: QFontDatabase es estático en PyQt6, no se instancia
    # Usar métodos estáticos directamente
    loaded_fonts = []
    
    # Fuentes a cargar
    font_files = [
        "Inter-Regular.ttf",
        "Inter-Medium.ttf",
        "Inter-SemiBold.ttf",
        "Inter-Bold.ttf",
        "JetBrainsMono-Regular.ttf",
    ]
    
    for font_file in font_files:
        font_path = fonts_dir / font_file
        if font_path.exists():
            try:
                # CRITICAL FIX: QFontDatabase es estático en PyQt6, usar métodos estáticos
                # #region agent log
                if agent_log_enabled():
                    import json, time
                    try:
                        from app.utils.path_utils import get_debug_log_path_str  # FIX: agent_log_enabled ya importado arriba
                        with open(get_debug_log_path_str(), "a") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H2","location":"themes/loader.py:load_fonts","message":"Before addApplicationFont","data":{"font_file":font_file},"timestamp":int(time.time()*1000)})+"\n")
                    except Exception as e: logger.debug("Writing before addApplicationFont log: %s", e)
                # #endregion
                font_id = QtGui.QFontDatabase.addApplicationFont(str(font_path))
                
                # #region agent log
                if agent_log_enabled():
                    try:
                        from app.utils.path_utils import get_debug_log_path_str
                        with open(get_debug_log_path_str(), "a") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H2","location":"themes/loader.py:load_fonts","message":"After addApplicationFont","data":{"font_id":font_id,"font_file":font_file},"timestamp":int(time.time()*1000)})+"\n")
                    except Exception as e: logger.debug("Writing after addApplicationFont log: %s", e)
                # #endregion
                
                if font_id != -1:
                    # #region agent log
                    if agent_log_enabled():
                        try:
                            from app.utils.path_utils import get_debug_log_path_str
                            with open(get_debug_log_path_str(), "a") as f:
                                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H2","location":"themes/loader.py:load_fonts","message":"Before applicationFontFamilies","data":{"font_id":font_id},"timestamp":int(time.time()*1000)})+"\n")
                        except Exception as e: logger.debug("Writing before applicationFontFamilies log: %s", e)
                    # #endregion
                    families = QtGui.QFontDatabase.applicationFontFamilies(font_id)
                    
                    # #region agent log
                    if agent_log_enabled():
                        try:
                            from app.utils.path_utils import get_debug_log_path_str
                            with open(get_debug_log_path_str(), "a") as f:
                                f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H2","location":"themes/loader.py:load_fonts","message":"After applicationFontFamilies","data":{"families":families if families else []},"timestamp":int(time.time()*1000)})+"\n")
                        except Exception as e: logger.debug("Writing after applicationFontFamilies log: %s", e)
                    # #endregion
                    
                    if families:
                        loaded_fonts.append(families[0])
                        logger.debug(f"✅ Fuente cargada: {families[0]} desde {font_file}")
                else:
                    logger.warning(f"⚠️ No se pudo cargar fuente: {font_file}")
            except Exception as e:
                # #region agent log
                if agent_log_enabled():
                    try:
                        from app.utils.path_utils import get_debug_log_path_str
                        with open(get_debug_log_path_str(), "a") as f:
                            f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"H2","location":"themes/loader.py:load_fonts","message":"Exception loading font","data":{"error":str(e),"error_type":type(e).__name__,"font_file":font_file},"timestamp":int(time.time()*1000)})+"\n")
                    except Exception as e2: logger.debug("Writing font exception log: %s", e2)
                # #endregion
                logger.warning(f"⚠️ Error cargando fuente {font_file}: {e}")
        else:
            logger.debug(f"⏭️ Fuente no encontrada: {font_file} (opcional)")
    
    if loaded_fonts:
        # Establecer fuente por defecto
        default_font = QtGui.QFont(loaded_fonts[0] if loaded_fonts else "Arial")
        default_font.setPointSize(10)
        app.setFont(default_font)
        logger.info(f"✅ {len(loaded_fonts)} fuentes cargadas: {', '.join(loaded_fonts)}")
        return True
    
    logger.warning("⚠️ No se cargaron fuentes personalizadas")
    return False
