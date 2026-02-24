from datetime import datetime
import logging
from pathlib import Path

# Directorio seguro para exports
SAFE_EXPORT_DIR = Path(__file__).parent.parent.parent / 'data' / 'exports'


def validate_export_path(filename: str) -> Path:
    """Validate and sanitize export filename to prevent path traversal."""
    SAFE_EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    if '..' in filename or filename.startswith('/') or filename.startswith('\\'):
        raise ValueError(f"Invalid filename: path traversal detected in '{filename}'")

    safe_name = Path(filename).name

    if not safe_name.endswith(('.pdf', '.txt', '.csv', '.xlsx')):
        safe_name = safe_name + '.pdf'

    full_path = (SAFE_EXPORT_DIR / safe_name).resolve()

    if not str(full_path).startswith(str(SAFE_EXPORT_DIR.resolve())):
        raise ValueError("Invalid filename: path outside allowed directory")

    return full_path


def export_sales_summary_pdf(data, filename):
    """Export sales summary to PDF with path validation."""
    safe_path = validate_export_path(filename)

    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas

        c = canvas.Canvas(str(safe_path), pagesize=letter)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, 750, "REPORTE DE VENTAS")
        c.setFont("Helvetica", 10)
        c.drawString(50, 730, f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

        y = 700
        for item in data:
            text = str(item)
            c.drawString(50, y, text[:80])
            y -= 20
            if y < 50:
                c.showPage()
                y = 750

        c.save()
        logging.info(f"PDF exported successfully to {safe_path}")
    except ImportError:
        txt_path = safe_path.with_suffix('.txt')
        with open(txt_path, 'w') as f:
            f.write("REPORTE DE VENTAS\n")
            f.write(f"Generado: {datetime.now()}\n\n")
            for item in data:
                f.write(f"{item}\n")
        logging.warning(f"Reportlab not available, exported as TXT to {txt_path}")
    except Exception as e:
        logging.error(f"Error exporting PDF: {e}")

def export_top_products_pdf(data, filename):
    """Export top products to PDF with path validation."""
    safe_path = validate_export_path(filename)

    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas

        c = canvas.Canvas(str(safe_path), pagesize=letter)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, 750, "TOP PRODUCTOS")
        c.setFont("Helvetica", 10)
        c.drawString(50, 730, f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

        y = 700
        for idx, item in enumerate(data[:20], 1):
            text = f"{idx}. {item.get('name', 'N/A')} - Vendidos: {item.get('qty', 0)}"
            c.drawString(50, y, text)
            y -= 20
            if y < 50:
                break

        c.save()
        logging.info(f"Top products PDF exported to {safe_path}")
    except ImportError:
        txt_path = safe_path.with_suffix('.txt')
        with open(txt_path, 'w') as f:
            f.write("TOP PRODUCTOS\n\n")
            for idx, item in enumerate(data[:20], 1):
                f.write(f"{idx}. {item.get('name', 'N/A')} - {item.get('qty', 0)}\n")
        logging.warning(f"Exportado como TXT to {txt_path}")
    except Exception as e:
        logging.error(f"Error: {e}")

def export_daily_sales_pdf(data, filename):
    """Export daily sales to PDF"""
    export_sales_summary_pdf(data, filename)

def export_credit_report_pdf(data, filename):
    """Export credit report to PDF with path validation."""
    safe_path = validate_export_path(filename)

    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas

        c = canvas.Canvas(str(safe_path), pagesize=letter)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, 750, "REPORTE DE CRÉDITOS")
        c.setFont("Helvetica", 10)

        y = 720
        total = 0
        for customer in data:
            balance = float(customer.get('credit_balance', 0))
            total += balance
            text = f"{customer.get('name', 'N/A')}: ${balance:,.2f}"
            c.drawString(50, y, text)
            y -= 20
            if y < 50:
                c.showPage()
                y = 750

        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y - 20, f"TOTAL ADEUDADO: ${total:,.2f}")
        c.save()
        logging.info(f"Credit report exported to {safe_path}")
    except ImportError:
        txt_path = safe_path.with_suffix('.txt')
        with open(txt_path, 'w') as f:
            f.write("REPORTE DE CRÉDITOS\n\n")
            total = 0
            for customer in data:
                balance = float(customer.get('credit_balance', 0))
                total += balance
                f.write(f"{customer.get('name', 'N/A')}: ${balance:,.2f}\n")
            f.write(f"\nTOTAL: ${total:,.2f}\n")
        logging.warning(f"Exportado como TXT to {txt_path}")
    except Exception as e:
        logging.error(f"Error: {e}")

def export_layaway_report_pdf(data, filename):
    """Export layaway report to PDF"""
    export_sales_summary_pdf(data, filename)
