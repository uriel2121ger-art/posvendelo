"""
TITAN POS - Product Exports

Export products to CSV and Excel formats.
"""

from typing import Any, Dict, List
import csv


def export_products_to_csv(products: List[Dict[str, Any]], path: str) -> None:
    """
    Export products to a CSV file.

    Args:
        products: List of product dictionaries
        path: Output file path
    """
    headers = [
        "SKU",
        "Descripcion",
        "Tipo",
        "Precio",
        "Mayoreo",
        "Departamento",
        "Proveedor",
        "Inventario",
        "Min",
        "Max",
        "Favorito",
    ]

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        for p in products:
            writer.writerow([
                p.get("sku", ""),
                p.get("name", ""),
                p.get("sale_type", ""),
                p.get("price", ""),
                p.get("price_wholesale", ""),
                p.get("category") or p.get("department") or "",
                p.get("provider") or "",
                p.get("stock", ""),
                p.get("min_stock", ""),
                p.get("max_stock", ""),
            ])


def export_products_to_excel(products: List[Dict[str, Any]], path: str) -> None:
    """
    Export products to an Excel file.

    Args:
        products: List of product dictionaries
        path: Output file path

    Raises:
        RuntimeError: If openpyxl is not available
    """
    try:
        from openpyxl import Workbook
    except ImportError as exc:
        raise RuntimeError("openpyxl no esta disponible para exportar a Excel") from exc

    wb = Workbook()
    ws = wb.active
    ws.title = "Productos"

    headers = [
        "SKU",
        "Descripcion",
        "Tipo",
        "Precio",
        "Mayoreo",
        "Departamento",
        "Proveedor",
        "Inventario",
        "Min",
        "Max",
    ]
    ws.append(headers)

    for p in products:
        ws.append([
            p.get("sku", ""),
            p.get("name", ""),
            p.get("sale_type", ""),
            p.get("price", ""),
            p.get("price_wholesale", ""),
            p.get("category") or p.get("department") or "",
            p.get("provider") or "",
            p.get("stock", ""),
            p.get("min_stock", ""),
            p.get("max_stock", ""),
        ])

    wb.save(path)
