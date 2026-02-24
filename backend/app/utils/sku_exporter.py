"""
TITAN POS - SKU Export Utility
===============================

Exporta SKUs generados a múltiples formatos para integración con:
- Sistemas de inventario externos
- Impresoras de etiquetas
- APIs de terceros
- Hojas de cálculo

Formatos soportados: CSV, JSON, TXT
"""

from typing import Dict, List
import csv
from datetime import datetime
import json
import logging

logger = logging.getLogger("SKU_EXPORTER")

class SKUExporter:
    """Exportador de SKUs a múltiples formatos."""
    
    def __init__(self, db_manager):
        """
        Args:
            db_manager: Instancia de DatabaseManager
        """
        self.db = db_manager
    
    def export_to_csv(self, skus: List[str], filepath: str) -> bool:
        """
        Exporta lista de SKUs a archivo CSV.
        
        Args:
            skus: Lista de códigos SKU
            filepath: Ruta del archivo de salida
            
        Returns:
            True si exitoso, False si falla
        """
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['SKU', 'Prefix', 'Sequence', 'Checksum', 'Generated_At'])
                
                for sku in skus:
                    if len(sku) == 13:
                        prefix = sku[:2]
                        sequence = sku[2:12]
                        checksum = sku[12]
                    else:
                        prefix = sequence = checksum = ''
                    
                    writer.writerow([
                        sku,
                        prefix,
                        sequence,
                        checksum,
                        datetime.now().isoformat()
                    ])
            
            logger.info(f"✓ Exported {len(skus)} SKUs to CSV: {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"CSV export failed: {e}")
            return False
    
    def export_to_json(self, skus: List[str], filepath: str) -> bool:
        """
        Exporta SKUs a formato JSON.
        
        Args:
            skus: Lista de códigos SKU
            filepath: Ruta del archivo de salida
            
        Returns:
            True si exitoso
        """
        try:
            data = {
                "export_date": datetime.now().isoformat(),
                "total_skus": len(skus),
                "skus": []
            }
            
            for sku in skus:
                if len(sku) == 13:
                    sku_obj = {
                        "code": sku,
                        "prefix": sku[:2],
                        "sequence": sku[2:12],
                        "checksum": sku[12],
                        "format": "EAN-13"
                    }
                else:
                    sku_obj = {
                        "code": sku,
                        "format": "custom"
                    }
                
                data["skus"].append(sku_obj)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✓ Exported {len(skus)} SKUs to JSON: {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"JSON export failed: {e}")
            return False
    
    def export_to_txt(self, skus: List[str], filepath: str) -> bool:
        """
        Exporta SKUs a archivo de texto simple (un SKU por línea).
        
        Args:
            skus: Lista de códigos SKU
            filepath: Ruta del archivo de salida
            
        Returns:
            True si exitoso
        """
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"# TITAN POS - SKU Export\n")
                f.write(f"# Generated: {datetime.now().isoformat()}\n")
                f.write(f"# Total: {len(skus)} SKUs\n")
                f.write("#" + "="*50 + "\n\n")
                
                for sku in skus:
                    f.write(f"{sku}\n")
            
            logger.info(f"✓ Exported {len(skus)} SKUs to TXT: {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"TXT export failed: {e}")
            return False
    
    def export_products_with_skus(self, prefix: str = None, filepath: str = None, format: str = 'csv') -> bool:
        """
        Exporta productos con sus SKUs desde la base de datos.
        
        Args:
            prefix: Filtrar por prefijo (opcional)
            filepath: Ruta del archivo de salida
            format: 'csv' o 'json'
            
        Returns:
            True si exitoso
        """
        try:
            if prefix:
                query = """
                    SELECT sku, name, price, stock, department
                    FROM products
                    WHERE sku LIKE %s AND CHAR_LENGTH(sku) = 13
                    ORDER BY sku
                """
                products = self.db.execute_query(query, (f"{prefix}%",))
            else:
                query = """
                    SELECT sku, name, price, stock, department
                    FROM products
                    WHERE CHAR_LENGTH(sku) = 13
                    ORDER BY sku
                """
                products = self.db.execute_query(query)
            
            products_list = [dict(p) for p in products]
            
            if format == 'csv':
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    if products_list:
                        writer = csv.DictWriter(f, fieldnames=products_list[0].keys())
                        writer.writeheader()
                        writer.writerows(products_list)
            elif format == 'json':
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump({
                        "export_date": datetime.now().isoformat(),
                        "total": len(products_list),
                        "products": products_list
                    }, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✓ Exported {len(products_list)} products to {format.upper()}")
            return True
            
        except Exception as e:
            logger.error(f"Product export failed: {e}")
            return False

# ==================== CONVENIENCE FUNCTIONS ====================

def quick_export_skus_csv(skus: List[str], filename: str = None) -> str:
    """
    Exportación rápida de SKUs a CSV en el directorio data/exports.
    
    Args:
        skus: Lista de SKUs
        filename: Nombre del archivo (opcional, se genera automáticamente)
        
    Returns:
        Ruta del archivo generado
    """
    import os
    from pathlib import Path

    # Crear directorio de exports si no existe
    try:
        from src.utils.paths import get_data_dir
        data_dir = get_data_dir()
    except Exception:
        data_dir = os.getcwd()
    
    export_dir = Path(data_dir) / "exports"
    export_dir.mkdir(exist_ok=True)
    
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"skus_export_{timestamp}.csv"
    
    filepath = export_dir / filename
    
    # Simple CSV export
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['SKU'])
        for sku in skus:
            writer.writerow([sku])
    
    return str(filepath)

if __name__ == "__main__":
    # Test de ejemplo
    test_skus = [
        "2000000000015",
        "2000000000022",
        "2100000000012",
        "2100000000029"
    ]
    
    print("Exportando SKUs de prueba...")
    filepath = quick_export_skus_csv(test_skus, "test_skus.csv")
    print(f"✓ Archivo generado: {filepath}")
