"""
POSVENDELO — ESC/POS Receipt Builder

Pure-bytes ESC/POS generator for 58mm and 80mm thermal printers.
No external dependencies — outputs raw bytes for CUPS lp -o raw.
"""

from __future__ import annotations

from datetime import datetime

# ---------------------------------------------------------------------------
# ESC/POS command constants
# ---------------------------------------------------------------------------

INIT = b"\x1B\x40"                  # Initialize printer
BOLD_ON = b"\x1B\x45\x01"
BOLD_OFF = b"\x1B\x45\x00"
ALIGN_LEFT = b"\x1B\x61\x00"
ALIGN_CENTER = b"\x1B\x61\x01"
ALIGN_RIGHT = b"\x1B\x61\x02"
DOUBLE_HW_ON = b"\x1D\x21\x11"     # Double height + double width
DOUBLE_HW_OFF = b"\x1D\x21\x00"
CUT_FULL = b"\x1D\x56\x00"         # Full cut
CUT_PARTIAL = b"\x1D\x56\x01"      # Partial cut
DRAWER_KICK = b"\x1B\x70\x00\x19\xFA"  # Kick pin 2, 25ms on, 250ms off
CODEPAGE_850 = b"\x1B\x74\x02"     # Select cp850 for Spanish accents
LF = b"\x0A"


def _encode(text: str) -> bytes:
    """Encode text to cp850 (best-effort for accented Spanish)."""
    return text.encode("cp850", errors="replace")


# ---------------------------------------------------------------------------
# ReceiptBuilder
# ---------------------------------------------------------------------------

class ReceiptBuilder:
    """Fluent builder for ESC/POS receipt byte stream."""

    def __init__(self, char_width: int = 48):
        self._cw = char_width
        self._buf: list[bytes] = [INIT, CODEPAGE_850]

    # -- Text formatting --

    def center(self, text: str) -> "ReceiptBuilder":
        self._buf += [ALIGN_CENTER, _encode(text), LF, ALIGN_LEFT]
        return self

    def left(self, text: str) -> "ReceiptBuilder":
        self._buf += [ALIGN_LEFT, _encode(text), LF]
        return self

    def right(self, text: str) -> "ReceiptBuilder":
        self._buf += [ALIGN_RIGHT, _encode(text), LF, ALIGN_LEFT]
        return self

    def bold(self, text: str, align: str = "left") -> "ReceiptBuilder":
        if align == "center":
            self._buf.append(ALIGN_CENTER)
        self._buf += [BOLD_ON, _encode(text), LF, BOLD_OFF]
        if align == "center":
            self._buf.append(ALIGN_LEFT)
        return self

    def double_size(self, text: str) -> "ReceiptBuilder":
        self._buf += [ALIGN_CENTER, DOUBLE_HW_ON, _encode(text), LF, DOUBLE_HW_OFF, ALIGN_LEFT]
        return self

    # -- Layout helpers --

    def columns(self, left: str, right: str) -> "ReceiptBuilder":
        """Two-column line: left-aligned text + right-aligned value."""
        space = self._cw - len(left) - len(right)
        if space < 1:
            space = 1
        line = left + " " * space + right
        self._buf += [_encode(line), LF]
        return self

    def three_columns(self, col1: str, col2: str, col3: str) -> "ReceiptBuilder":
        """Three-column line for item listings: CANT | PRODUCTO | IMPORTE."""
        w1, w3 = 5, 10
        w2 = self._cw - w1 - w3
        c1 = col1[:w1].ljust(w1)
        c3 = col3[:w3].rjust(w3)
        c2 = col2[:w2].ljust(w2)
        self._buf += [_encode(c1 + c2 + c3), LF]
        return self

    def line(self, char: str = "-") -> "ReceiptBuilder":
        self._buf += [_encode(char * self._cw), LF]
        return self

    # -- Printer commands --

    def cut(self, full: bool = False) -> "ReceiptBuilder":
        self._buf += [LF, LF, LF, CUT_FULL if full else CUT_PARTIAL]
        return self

    def open_drawer(self) -> "ReceiptBuilder":
        self._buf.append(DRAWER_KICK)
        return self

    def feed(self, lines: int = 1) -> "ReceiptBuilder":
        self._buf += [LF] * lines
        return self

    def build(self) -> bytes:
        return b"".join(self._buf)


# ---------------------------------------------------------------------------
# High-level receipt builder
# ---------------------------------------------------------------------------

def build_sale_receipt(
    sale: dict,
    items: list[dict],
    config: dict,
    char_width: int = 48,
) -> bytes:
    """Build a complete sale receipt from sale data + app_config.

    Args:
        sale: dict with keys folio_visible, timestamp, payment_method, total,
              subtotal, tax, discount, cash_received, change.
        items: list of dicts with product_name, qty, price, subtotal.
        config: app_config row dict (business_name, business_rfc, etc.).
        char_width: 32 for 58mm, 48 for 80mm paper.

    Returns:
        Raw ESC/POS bytes ready to send via CUPS.
    """
    rb = ReceiptBuilder(char_width)
    mode = config.get("receipt_mode", "basic")
    cut_full = config.get("receipt_cut_type", "partial") == "full"

    # --- Header: business info ---
    biz_name = config.get("business_name", "")
    if biz_name:
        rb.double_size(biz_name)

    legal_name = config.get("business_legal_name", "")
    if legal_name:
        rb.center(legal_name)

    if mode == "fiscal":
        rfc = config.get("business_rfc", "")
        regimen = config.get("business_regimen", "")
        if rfc:
            rb.center(f"RFC: {rfc}")
        if regimen:
            rb.center(regimen)

    biz_addr = config.get("business_address", "")
    if biz_addr:
        rb.center(biz_addr)

    biz_phone = config.get("business_phone", "")
    if biz_phone:
        rb.center(f"Tel: {biz_phone}")

    rb.line("=")

    # --- Sale info ---
    folio = sale.get("folio_visible") or f"#{sale.get('id', '?')}"
    ts_raw = sale.get("timestamp", "")
    try:
        ts = datetime.fromisoformat(str(ts_raw)).strftime("%d/%m/%Y %H:%M")
    except (ValueError, TypeError):
        ts = str(ts_raw)[:16]

    rb.bold(f"Folio: {folio}", align="center")
    rb.center(ts)

    payment = sale.get("payment_method", "cash")
    payment_label = {
        "cash": "Efectivo",
        "card": "Tarjeta",
        "transfer": "Transferencia",
        "mixed": "Mixto",
    }.get(payment, payment)
    rb.center(f"Pago: {payment_label}")
    rb.line("-")

    # --- Items ---
    rb.three_columns("CANT", "PRODUCTO", "IMPORTE")
    rb.line("-")

    for item in items:
        qty = item.get("qty", 1)
        name = item.get("product_name") or item.get("name", "Producto")
        subtotal = item.get("subtotal", 0)
        price = item.get("price", 0)

        qty_str = str(int(qty)) if float(qty) == int(qty) else f"{qty:.2f}"
        rb.three_columns(qty_str, name[:char_width - 16], f"${subtotal:,.2f}")

        if float(qty) > 1:
            rb.left(f"  @${price:,.2f} c/u")

    rb.line("-")

    # --- Totals ---
    sale_subtotal = float(sale.get("subtotal", 0))
    sale_discount = float(sale.get("discount", 0))
    sale_tax = float(sale.get("tax", 0))
    sale_total = float(sale.get("total", 0))

    rb.columns("Subtotal:", f"${sale_subtotal:,.2f}")
    if sale_discount > 0:
        rb.columns("Descuento:", f"-${sale_discount:,.2f}")
    if mode == "fiscal":
        rb.columns("IVA 16%:", f"${sale_tax:,.2f}")

    rb.line("=")
    rb.feed(1)
    rb.double_size(f"TOTAL: ${sale_total:,.2f}")
    rb.feed(1)

    # --- Change (cash payments) ---
    if payment == "cash":
        received = float(sale.get("cash_received", 0))
        change = float(sale.get("change_given", 0))
        if received > 0:
            rb.columns("Recibido:", f"${received:,.2f}")
            rb.columns("Cambio:", f"${change:,.2f}")

    rb.line("-")

    # --- Fiscal disclaimer ---
    if mode == "fiscal":
        rb.feed(1)
        rb.center("* COMPROBANTE FISCAL *")
        rb.center("Este ticket es un comprobante")
        rb.center("simplificado de venta.")

    # --- Footer ---
    footer = config.get("business_footer", "Gracias por su compra")
    if footer:
        rb.feed(1)
        rb.center(footer)

    rb.feed(1)
    rb.cut(full=cut_full)

    return rb.build()


def build_shift_report(
    turn: dict,
    summary: dict,
    config: dict,
    char_width: int = 48,
) -> bytes:
    """Build a shift cut report for the thermal printer.

    Args:
        turn: dict with id, initial_cash, final_cash, status, start_timestamp, end_timestamp.
        summary: dict from get_turn_summary (sales_count, total_sales, expected_cash, etc.).
        config: app_config row dict (business_name, etc.).
        char_width: 32 for 58mm, 48 for 80mm paper.
    """
    rb = ReceiptBuilder(char_width)
    cut_full = config.get("receipt_cut_type", "partial") == "full"

    biz_name = config.get("business_name", "") or "POSVENDELO"
    rb.double_size(biz_name)
    rb.line("=")
    rb.bold("CORTE DE CAJA", align="center")
    rb.line("-")

    # Turn info
    rb.columns("Turno ID:", str(turn.get("id", "?")))
    start = turn.get("start_timestamp", "")
    try:
        ts = datetime.fromisoformat(str(start)).strftime("%d/%m/%Y %H:%M")
    except (ValueError, TypeError):
        ts = str(start)[:16]
    rb.columns("Apertura:", ts)

    end = turn.get("end_timestamp", "")
    if end:
        try:
            te = datetime.fromisoformat(str(end)).strftime("%d/%m/%Y %H:%M")
        except (ValueError, TypeError):
            te = str(end)[:16]
        rb.columns("Cierre:", te)

    rb.line("-")
    rb.bold("VENTAS")

    sales_count = summary.get("sales_count", 0)
    total_sales = float(summary.get("total_sales", 0))
    rb.columns("Num. ventas:", str(sales_count))
    rb.columns("Total ventas:", f"${total_sales:,.2f}")

    # Sales by method
    sales_by_method = summary.get("sales_by_method", [])
    method_labels = {"cash": "Efectivo", "card": "Tarjeta", "transfer": "Transferencia", "mixed": "Mixto"}
    for row in sales_by_method:
        method = str(row.get("payment_method", ""))
        label = method_labels.get(method, method)
        count = row.get("count", 0)
        total = float(row.get("total", 0))
        rb.columns(f"  {label} ({count}):", f"${total:,.2f}")

    rb.line("-")
    rb.bold("EFECTIVO")

    initial = float(summary.get("initial_cash", turn.get("initial_cash", 0)))
    cash_in = float(summary.get("cash_in", 0))
    cash_out = float(summary.get("cash_out", 0))
    expected = float(summary.get("expected_cash", 0))
    final = float(turn.get("final_cash", 0))
    difference = final - expected

    rb.columns("Fondo inicial:", f"${initial:,.2f}")
    if cash_in > 0:
        rb.columns("Entradas:", f"${cash_in:,.2f}")
    if cash_out > 0:
        rb.columns("Retiros/Gastos:", f"-${cash_out:,.2f}")
    rb.line("-")
    rb.columns("Esperado:", f"${expected:,.2f}")
    rb.columns("Contado:", f"${final:,.2f}")
    rb.line("=")
    rb.feed(1)

    diff_str = f"${abs(difference):,.2f}"
    if difference > 0.005:
        rb.double_size(f"SOBRANTE: +{diff_str}")
    elif difference < -0.005:
        rb.double_size(f"FALTANTE: -{diff_str}")
    else:
        rb.double_size("CUADRADO $0.00")

    rb.feed(1)
    rb.center(f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    rb.feed(1)
    rb.cut(full=cut_full)

    return rb.build()


def build_test_receipt(config: dict, char_width: int = 48) -> bytes:
    """Build a test receipt to verify printer setup."""
    rb = ReceiptBuilder(char_width)

    biz_name = config.get("business_name", "") or "POSVENDELO"
    rb.double_size(biz_name)
    rb.line("=")
    rb.bold("TICKET DE PRUEBA", align="center")
    rb.center(datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
    rb.line("-")
    rb.columns("Ancho papel:", f"{config.get('receipt_paper_width', 80)}mm")
    rb.columns("Caracteres:", str(char_width))
    rb.columns("Modo:", config.get("receipt_mode", "basic"))
    rb.columns("Corte:", config.get("receipt_cut_type", "partial"))
    rb.line("-")
    rb.three_columns("CANT", "PRODUCTO", "IMPORTE")
    rb.line("-")
    rb.three_columns("2", "Coca-Cola 600ml", "$30.00")
    rb.three_columns("1", "Pan Bimbo Grande", "$58.50")
    rb.three_columns("3", "Sabritas Adobadas", "$54.00")
    rb.line("=")
    rb.double_size("TOTAL: $142.50")
    rb.feed(1)
    rb.center("Impresora configurada correctamente")
    rb.center("Acentos: accion, nino, cafe")
    rb.feed(1)

    cut_full = config.get("receipt_cut_type", "partial") == "full"
    rb.cut(full=cut_full)

    return rb.build()
