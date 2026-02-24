"""
TITAN POS - Icon Manager
Gestor de iconos Lucide Icons para el tema Cyber Night.
"""

import logging
from pathlib import Path
from typing import Optional, Dict

from PyQt6 import QtGui, QtWidgets
from app.utils.path_utils import get_debug_log_path_str, get_debug_log_path, agent_log_enabled

logger = logging.getLogger(__name__)


class IconManager:
    """
    Gestor de iconos Lucide Icons.
    
    Carga iconos SVG desde app/ui/assets/icons/ y los convierte
    a QIcon para uso en PyQt6.
    """
    
    _instance: Optional['IconManager'] = None
    _icons_cache: Dict[str, QtGui.QIcon] = {}
    
    def __init__(self):
        self.icons_dir = Path(__file__).parent.parent / "assets" / "icons"
        self._load_icons()
    
    @classmethod
    def instance(cls) -> 'IconManager':
        """Obtiene la instancia singleton."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def _load_icons(self):
        """Carga todos los iconos disponibles."""
        # #region agent log
        if agent_log_enabled():
            import json
            log_path = Path(get_debug_log_path_str())
            try:
                with open(log_path, 'a') as f:
                    f.write(json.dumps({
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "H1",
                        "location": "icon_manager.py:_load_icons:39",
                        "message": "Checking icons directory",
                        "data": {"icons_dir": str(self.icons_dir), "exists": self.icons_dir.exists()},
                        "timestamp": int(__import__('time').time() * 1000)
                    }) + "\n")
            except Exception as e: logger.debug("Writing icons directory check to log: %s", e)
        # #endregion

        if not self.icons_dir.exists():
            logger.warning(f"Directorio de iconos no existe: {self.icons_dir}")
            return
        
        svg_files = list(self.icons_dir.glob("*.svg"))
        logger.info(f"📦 Cargando {len(svg_files)} iconos desde {self.icons_dir}")
        
        # #region agent log
        if agent_log_enabled():
            try:
                with open(log_path, 'a') as f:
                    f.write(json.dumps({
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "H1",
                        "location": "icon_manager.py:_load_icons:45",
                        "message": "Found SVG files",
                        "data": {"count": len(svg_files), "files": [str(f) for f in svg_files[:5]]},
                        "timestamp": int(__import__('time').time() * 1000)
                    }) + "\n")
            except Exception as e: logger.debug("Writing SVG files found to log: %s", e)
        # #endregion

        for svg_file in svg_files:
            icon_name = svg_file.stem
            
            # #region agent log
            if agent_log_enabled():
                try:
                    file_size = svg_file.stat().st_size
                    file_content_preview = ""
                    if file_size > 0:
                        with open(svg_file, 'r', encoding='utf-8') as f:
                            file_content_preview = f.read(100)
                    with open(log_path, 'a') as f:
                        f.write(json.dumps({
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "H1",
                            "location": "icon_manager.py:_load_icons:48",
                            "message": "Loading icon file",
                            "data": {
                                "icon_name": icon_name,
                                "file_path": str(svg_file),
                                "file_size": file_size,
                                "content_preview": file_content_preview[:50] if file_content_preview else "EMPTY"
                            },
                            "timestamp": int(__import__('time').time() * 1000)
                        }) + "\n")
                except Exception as log_err: logger.debug("Writing icon file details to log: %s", log_err)
            # #endregion

            try:
                icon = QtGui.QIcon(str(svg_file))
                self._icons_cache[icon_name] = icon
                
                # #region agent log
                if agent_log_enabled():
                    try:
                        with open(log_path, 'a') as f:
                            f.write(json.dumps({
                                "sessionId": "debug-session",
                                "runId": "run1",
                                "hypothesisId": "H2",
                                "location": "icon_manager.py:_load_icons:52",
                                "message": "Icon loaded successfully",
                                "data": {"icon_name": icon_name},
                                "timestamp": int(__import__('time').time() * 1000)
                            }) + "\n")
                    except Exception as e: logger.debug("Writing icon load success to log: %s", e)
                # #endregion
            except Exception as e:
                # #region agent log
                if agent_log_enabled():
                    try:
                        with open(log_path, 'a') as f:
                            f.write(json.dumps({
                                "sessionId": "debug-session",
                                "runId": "run1",
                                "hypothesisId": "H2",
                                "location": "icon_manager.py:_load_icons:54",
                                "message": "Icon load failed",
                                "data": {"icon_name": icon_name, "error": str(e), "error_type": type(e).__name__},
                                "timestamp": int(__import__('time').time() * 1000)
                            }) + "\n")
                    except Exception as e2: logger.debug("Writing icon load failure to log: %s", e2)
                # #endregion
                logger.warning(f"⚠️  No se pudo cargar icono {icon_name}: {e}")
    
    def get_icon(self, icon_name: str, color: Optional[str] = None, size: int = 24) -> Optional[QtGui.QIcon]:
        """
        Obtiene un icono por nombre.
        
        Args:
            icon_name: Nombre del icono (sin extensión .svg)
            color: Color para aplicar al icono (hex, ej: "#00F2FF")
            size: Tamaño del icono en píxeles
        
        Returns:
            QIcon o None si no se encuentra
        """
        # Buscar en caché
        if icon_name in self._icons_cache:
            icon = self._icons_cache[icon_name]
            
            # Aplicar color si se especifica
            if color:
                icon = self._apply_color(icon, color, size)
            
            return icon
        
        # Intentar cargar directamente
        icon_path = self.icons_dir / f"{icon_name}.svg"
        if icon_path.exists():
            try:
                icon = QtGui.QIcon(str(icon_path))
                self._icons_cache[icon_name] = icon
                
                if color:
                    icon = self._apply_color(icon, color, size)
                
                return icon
            except Exception as e:
                logger.warning(f"⚠️  Error cargando icono {icon_name}: {e}")
        
        logger.debug(f"⚠️  Icono no encontrado: {icon_name}")
        return None
    
    def _apply_color(self, icon: QtGui.QIcon, color: str, size: int) -> QtGui.QIcon:
        """
        Aplica un color a un icono SVG.
        
        Nota: PyQt6 no soporta fácilmente colorear SVGs directamente.
        Esta función es un placeholder para futuras mejoras.
        """
        # Por ahora, retornar el icono sin modificar
        # En el futuro, se podría usar QSvgRenderer para modificar el color
        return icon
    
    def get_pixmap(self, icon_name: str, size: int = 24, color: Optional[str] = None) -> Optional[QtGui.QPixmap]:
        """
        Obtiene un pixmap del icono.
        
        Args:
            icon_name: Nombre del icono
            size: Tamaño en píxeles
            color: Color para aplicar
        
        Returns:
            QPixmap o None
        """
        icon = self.get_icon(icon_name, color, size)
        if icon:
            return icon.pixmap(size, size)
        return None
    
    def list_icons(self) -> list:
        """Lista todos los iconos disponibles."""
        return list(self._icons_cache.keys())
    
    def has_icon(self, icon_name: str) -> bool:
        """Verifica si un icono existe."""
        return icon_name in self._icons_cache or (self.icons_dir / f"{icon_name}.svg").exists()


# Instancia global
icon_manager = IconManager.instance()

# Funciones helper
def get_icon(icon_name: str, color: Optional[str] = None, size: int = 24) -> Optional[QtGui.QIcon]:
    """Obtiene un icono (función helper)."""
    return icon_manager.get_icon(icon_name, color, size)


def get_pixmap(icon_name: str, size: int = 24, color: Optional[str] = None) -> Optional[QtGui.QPixmap]:
    """Obtiene un pixmap (función helper)."""
    return icon_manager.get_pixmap(icon_name, size, color)
