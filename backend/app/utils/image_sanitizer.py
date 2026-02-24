"""
Image Sanitizer - Limpieza de metadatos EXIF para evidencias
Elimina GPS, fecha original y datos del dispositivo
"""

from typing import Any, Dict, Optional
from datetime import datetime
import logging
import os
from pathlib import Path
import shutil

logger = logging.getLogger(__name__)

class ImageSanitizer:
    """
    Sanitizador de imágenes para eliminar metadatos EXIF.
    Previene discrepancias entre fecha de foto y fecha de documento.
    """
    
    EVIDENCE_PATH = Path(__file__).resolve().parent.parent.parent / 'docs/evidencias'
    
    def __init__(self):
        self.EVIDENCE_PATH.mkdir(parents=True, exist_ok=True)
    
    def sanitize_image(self, image_path: str, 
                       new_name: str = None) -> Dict[str, Any]:
        """
        Sanitiza una imagen eliminando todos los metadatos EXIF.
        
        Args:
            image_path: Ruta de la imagen original
            new_name: Nombre para la imagen sanitizada (opcional)
        
        Returns:
            Dict con ruta de imagen sanitizada
        """
        try:
            # Verificar que existe
            if not os.path.exists(image_path):
                return {'success': False, 'error': 'Imagen no encontrada'}
            
            # Intentar con PIL
            try:
                from PIL import Image
                return self._sanitize_with_pil(image_path, new_name)
            except ImportError:
                # Fallback sin PIL: solo copiar
                return self._sanitize_fallback(image_path, new_name)
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _sanitize_with_pil(self, image_path: str, 
                           new_name: str = None) -> Dict[str, Any]:
        """Sanitización usando PIL."""
        from PIL import Image

        # Abrir imagen con context manager para evitar resource leak
        with Image.open(image_path) as img:
            # Extraer solo los datos de píxeles (sin EXIF)
            data = list(img.getdata())
            img_mode = img.mode
            img_size = img.size

        # Crear nueva imagen sin metadatos
        img_clean = Image.new(img_mode, img_size)
        img_clean.putdata(data)

        # Generar nombre único
        if not new_name:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            ext = os.path.splitext(image_path)[1]
            new_name = f"evidence_{timestamp}{ext}"

        # Guardar imagen limpia
        output_path = self.EVIDENCE_PATH / new_name
        img_clean.save(str(output_path))
        img_clean.close()  # Explicitly close the new image

        # Verificar que EXIF fue removido
        with Image.open(str(output_path)) as img_check:
            exif_removed = not hasattr(img_check, '_getexif') or img_check._getexif() is None

        logger.info(f"🖼️ Imagen sanitizada: {new_name}")

        return {
            'success': True,
            'original_path': image_path,
            'sanitized_path': str(output_path),
            'filename': new_name,
            'exif_removed': exif_removed,
            'size': img_size
        }
    
    def _sanitize_fallback(self, image_path: str, 
                           new_name: str = None) -> Dict[str, Any]:
        """Fallback: solo copiar archivo."""
        if not new_name:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            ext = os.path.splitext(image_path)[1]
            new_name = f"evidence_{timestamp}{ext}"
        
        output_path = self.EVIDENCE_PATH / new_name
        shutil.copy2(image_path, str(output_path))
        
        return {
            'success': True,
            'original_path': image_path,
            'sanitized_path': str(output_path),
            'filename': new_name,
            'warning': 'PIL no disponible, metadatos pueden permanecer'
        }
    
    def get_exif_info(self, image_path: str) -> Dict[str, Any]:
        """Extrae información EXIF de una imagen (para diagnóstico)."""
        try:
            from PIL import Image
            from PIL.ExifTags import TAGS

            with Image.open(image_path) as img:
                exif_data = img._getexif()

                if not exif_data:
                    return {'has_exif': False, 'message': 'Sin metadatos EXIF'}

                # Decodificar tags
                decoded = {}
                dangerous_tags = []

                for tag_id, value in exif_data.items():
                    tag = TAGS.get(tag_id, tag_id)
                    decoded[tag] = str(value)[:100]  # Limitar longitud

                    # Detectar tags peligrosos
                    if tag in ['GPSInfo', 'DateTime', 'DateTimeOriginal',
                              'DateTimeDigitized', 'Make', 'Model']:
                        dangerous_tags.append(tag)

            return {
                'has_exif': True,
                'tag_count': len(decoded),
                'dangerous_tags': dangerous_tags,
                'sample_tags': dict(list(decoded.items())[:5])
            }

        except ImportError:
            return {'error': 'PIL no disponible'}
        except Exception as e:
            return {'error': str(e)}
    
    def batch_sanitize(self, image_paths: list) -> Dict[str, Any]:
        """Sanitiza múltiples imágenes."""
        results = []
        success = 0
        failed = 0
        
        for path in image_paths:
            result = self.sanitize_image(path)
            results.append(result)
            if result.get('success'):
                success += 1
            else:
                failed += 1
        
        return {
            'total': len(image_paths),
            'success': success,
            'failed': failed,
            'results': results
        }
