"""
CFDI Service - Orchestrates the complete CFDI generation process

Refactored: receives `db` (DB wrapper) directly instead of `core`.
Uses :name params and db.fetch/db.fetchrow/db.execute.
"""

from typing import Any, Dict, Optional
import asyncio
import logging
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import aiofiles

from modules.fiscal.constants import IVA_RATE, IVA_RATE_FLOAT
from modules.shared.constants import money

logger = logging.getLogger(__name__)


class CFDIService:
    def __init__(self, db, branch_id: int | None = None):
        self.db = db
        self.branch_id = branch_id
        self._facturapi = None

    async def _get_fiscal_config(self) -> dict:
        """Fetch fiscal config directly from DB."""
        if self.branch_id is None:
            return {}
        row = await self.db.fetchrow(
            "SELECT * FROM fiscal_config WHERE branch_id = :bid LIMIT 1",
            {"bid": self.branch_id},
        )
        return row or {}

    async def _resolve_branch_id_for_sale(self, sale_id: int) -> int | None:
        row = await self.db.fetchrow(
            "SELECT branch_id FROM sales WHERE id = :sid LIMIT 1",
            {"sid": sale_id},
        )
        branch_id = row.get("branch_id") if row else None
        if isinstance(branch_id, int) and branch_id > 0:
            self.branch_id = branch_id
            return branch_id
        return None

    @staticmethod
    def _resolve_customer_zip(customer_zip: str | None, fiscal_config: dict) -> str | None:
        candidate = (customer_zip or "").strip()
        if candidate and candidate != "00000":
            return candidate
        fiscal_zip = str(fiscal_config.get("codigo_postal") or fiscal_config.get("lugar_expedicion") or "").strip()
        if fiscal_zip and fiscal_zip != "00000":
            return fiscal_zip
        return None

    async def _get_sale_details(self, sale_id: int) -> Optional[dict]:
        """Fetch sale + items directly from DB."""
        sale = await self.db.fetchrow(
            "SELECT * FROM sales WHERE id = :sid", {"sid": sale_id}
        )
        if not sale:
            return None
        items = await self.db.fetch(
            "SELECT si.*, p.name AS product_name, p.sat_clave_prod_serv, p.sat_clave_unidad "
            "FROM sale_items si LEFT JOIN products p ON si.product_id = p.id "
            "WHERE si.sale_id = :sid",
            {"sid": sale_id},
        )
        return {**sale, "items": items}

    async def _get_facturapi(self):
        if self._facturapi is None:
            try:
                from modules.fiscal.facturapi_connector import Facturapi

                fiscal_cfg = await self._get_fiscal_config()
                api_key = fiscal_cfg.get("facturapi_api_key", "")

                if not api_key:
                    import os
                    api_key = os.getenv("FACTURAPI_KEY", "")

                if not api_key:
                    logger.warning("Facturapi API key no configurada en Settings -> Facturacion")
                    self._facturapi = False
                    return None

                self._facturapi = Facturapi(api_key)
                logger.info(f"Facturapi inicializado en modo: {self._facturapi.mode}")
            except Exception as e:
                logger.warning(f"Facturapi no disponible: {e}")
                self._facturapi = False
        return self._facturapi if self._facturapi else None

    async def generate_cfdi_via_facturapi(
        self,
        sale_id: int,
        customer_rfc: str,
        customer_name: Optional[str] = None,
        customer_regime: str = "616",
        uso_cfdi: str = "G03",
        customer_email: Optional[str] = None,
        customer_zip: str = "00000",
        payment_form_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            # Validate RFC format before any processing
            from modules.fiscal.rfc_validator import validate_rfc
            rfc_result = validate_rfc(customer_rfc)
            if not rfc_result.get('valid'):
                return {"success": False, "error": f"RFC inválido: {rfc_result.get('error', 'Formato incorrecto')}"}

            facturapi = await self._get_facturapi()
            if not facturapi:
                return {"success": False, "error": "Facturapi no configurado"}

            sale_data = await self._get_sale_details(sale_id)
            if not sale_data:
                return {"success": False, "error": f"Venta {sale_id} no encontrada"}

            def normalize_sat_key(sat_code: str) -> str:
                sat_code = str(sat_code).strip() if sat_code else "01010101"
                if len(sat_code) == 8:
                    return sat_code
                return sat_code.ljust(8, "0") if len(sat_code) < 8 else sat_code[:8]

            if customer_rfc.upper() == "XAXX010101000":
                return {"success": False, "error": "El RFC XAXX010101000 solo puede usarse en facturas globales."}

            if not customer_zip or customer_zip == "00000":
                fiscal_config = await self._get_fiscal_config()
                customer_zip = self._resolve_customer_zip(customer_zip, fiscal_config)
                if not customer_zip:
                    return {
                        "success": False,
                        "error": "Codigo postal del receptor o lugar de expedicion no configurado",
                    }

            items = []
            for item in sale_data.get("items", []):
                sat_code_raw = item.get("sat_code", item.get("sat_clave_prod_serv", "01010101"))
                items.append(
                    {
                        "quantity": money(item.get("quantity", item.get("qty", 1)) or 1),
                        "product": {
                            "description": item.get("name", item.get("product_name", "Producto")),
                            "product_key": normalize_sat_key(sat_code_raw),
                            "unit_key": item.get("sat_unit", item.get("sat_clave_unidad", "H87")),
                            "price": money(item.get("price", item.get("unit_price", 0))),
                            "taxes": [{"type": "IVA", "rate": IVA_RATE_FLOAT}],
                        },
                    }
                )

            if not items:
                return {"success": False, "error": "La venta no tiene productos"}

            if payment_form_override:
                payment_form = payment_form_override
                cfdi_payment_method = "PPD" if payment_form == "99" else "PUE"
            else:
                payment_method = sale_data.get("payment_method", "cash")
                payment_form_map = {
                    "cash": "01", "card": "04", "debit": "28", "transfer": "03",
                    "check": "02", "mixed": "99", "wallet": "05", "voucher": "08",
                    "usd": "01", "credit": "99",
                }
                payment_form = payment_form_map.get(payment_method, "01")
                # SAT: credit/mixed → PPD+99; everything else → PUE
                cfdi_payment_method = "PPD" if payment_method in ("credit", "mixed") else "PUE"

            invoice_data = {
                "customer": {
                    "legal_name": customer_name or "CLIENTE",
                    "tax_id": customer_rfc.upper(),
                    "tax_system": customer_regime,
                    "email": customer_email,
                    "address": {"zip": customer_zip},
                },
                "items": items,
                "payment_form": payment_form,
                "payment_method": cfdi_payment_method,
                "use": uso_cfdi,
                "folio_number": sale_id,
                "series": "F",
            }

            try:
                result = await facturapi.invoices.create(invoice_data)
            except Exception as e:
                error_str = str(e)
                if "product_key" in error_str.lower() or "couldn't find" in error_str.lower():
                    logger.warning("Facturapi rejected product_key, retrying with generic code '01010101'")
                    for item in items:
                        if "product" in item and "product_key" in item["product"]:
                            item["product"]["product_key"] = "01010101"
                    invoice_data["items"] = items
                    result = await facturapi.invoices.create(invoice_data)
                else:
                    raise

            if not isinstance(result, dict):
                return {"success": False, "error": f"Respuesta inesperada: {type(result).__name__}"}
            if not result.get("success"):
                return {"success": False, "error": result.get("error", "Error desconocido"), "details": result.get("details")}

            invoice = result["data"]
            uuid = invoice.get("uuid")
            invoice_id = invoice.get("id")

            from datetime import datetime

            cfdi_record = {
                "sale_id": sale_id,
                "uuid": uuid,
                "folio": sale_id,
                "serie": "POS",
                "rfc_receptor": customer_rfc.upper(),
                "nombre_receptor": customer_name or "PUBLICO EN GENERAL",
                "regimen_receptor": customer_regime,
                "uso_cfdi": uso_cfdi,
                "total": money(invoice.get("total", sale_data.get("total", 0))),
                "subtotal": money(sale_data.get("subtotal", 0)),
                "impuestos": money(sale_data.get("tax", 0)),
                "estado": "valid",
                "facturapi_id": invoice_id,
                "fecha_emision": datetime.now().isoformat(),
            }

            cfdi_id = await self._save_cfdi(cfdi_record)
            await self._promote_sale_to_serie_a(
                sale_id, uuid, {**sale_data, "customer_rfc": customer_rfc.upper()}
            )

            result_data = {
                "success": True,
                "cfdi_id": cfdi_id,
                "uuid": uuid,
                "facturapi_id": invoice_id,
                "total": invoice.get("total"),
                "pdf_url": f"https://www.facturapi.io/v2/invoices/{invoice_id}/pdf",
                "xml_url": f"https://www.facturapi.io/v2/invoices/{invoice_id}/xml",
                "status": invoice.get("status"),
                "mode": facturapi.mode,
            }

            if customer_email:
                try:
                    await facturapi.invoices.send_by_email(invoice_id, customer_email)
                    result_data["email_sent"] = True
                except Exception as e:
                    logger.warning(f"Error enviando email: {e}")
                    result_data["email_error"] = "Error al enviar email"

            return result_data
        except Exception as e:
            logger.error(f"Error generando CFDI: {e}", exc_info=True)
            return {"success": False, "error": "Error interno al generar CFDI"}

    async def cancel_cfdi_via_facturapi(self, uuid: str, motive: str = "02") -> Dict[str, Any]:
        try:
            facturapi = await self._get_facturapi()
            if not facturapi:
                return {"success": False, "error": "Facturapi no configurado"}

            cfdi = await self.db.fetchrow(
                "SELECT facturapi_id FROM cfdis WHERE uuid = :uuid", {"uuid": uuid}
            )
            if not cfdi:
                return {"success": False, "error": f"CFDI {uuid} no encontrado"}

            facturapi_id = cfdi.get("facturapi_id")
            if not facturapi_id:
                return {"success": False, "error": f"CFDI {uuid} no tiene ID de Facturapi"}

            result = await facturapi.invoices.cancel(facturapi_id, motive)
            if not isinstance(result, dict):
                return {"success": False, "error": f"Respuesta inesperada: {type(result).__name__}"}

            if result.get("success"):
                from datetime import datetime
                await self.db.execute(
                    "UPDATE cfdis SET estado = 'canceled', motivo_cancelacion = :motive, "
                    "fecha_cancelacion = :fecha WHERE uuid = :uuid",
                    {"motive": motive, "fecha": datetime.now().isoformat(), "uuid": uuid},
                )
            return result
        except Exception as e:
            logger.error(f"Error cancelando CFDI {uuid}: {e}", exc_info=True)
            return {"success": False, "error": "Error interno al cancelar CFDI"}

    async def _reserve_folio(self) -> int:
        """
        CFDI-021: Atomically reserve the next folio for the current branch.

        Uses UPDATE ... RETURNING to increment the counter and return the value
        that was just consumed in a single round-trip, eliminating the race
        condition that occurs when two concurrent requests both read the same
        folio_actual before either has incremented it.

        Returns the folio number to embed in the CFDI (the pre-increment value).
        """
        if not self.branch_id:
            raise ValueError("branch_id no establecido — no se puede reservar folio")
        folio_row = await self.db.fetchrow(
            "UPDATE fiscal_config "
            "SET folio_actual = folio_actual + 1 "
            "WHERE branch_id = :bid "
            "RETURNING folio_actual - 1 AS reserved_folio",
            {"bid": self.branch_id},
        )
        if not folio_row:
            raise ValueError(
                f"No se encontro configuracion fiscal para la sucursal {self.branch_id}"
            )
        reserved = folio_row.get("reserved_folio")
        logger.debug(f"Folio reservado: {reserved} (proximo sera {reserved + 1})")
        return reserved

    async def generate_cfdi_for_sale(
        self,
        sale_id: int,
        customer_rfc: str,
        customer_name: Optional[str] = None,
        customer_regime: str = "616",
        uso_cfdi: str = "G03",
        forma_pago: str = "01",
        customer_zip: str = "00000",
    ) -> Dict[str, Any]:
        try:
            sale_data = await self._get_sale_details(sale_id)
            if not sale_data:
                return {"success": False, "error": f"Venta {sale_id} no encontrada"}

            branch_id = sale_data.get("branch_id")
            if isinstance(branch_id, int) and branch_id > 0:
                self.branch_id = branch_id

            fiscal_config = await self._get_fiscal_config()
            if not fiscal_config or not fiscal_config.get("rfc_emisor"):
                return {"success": False, "error": "Configuracion fiscal no encontrada"}

            resolved_customer_zip = self._resolve_customer_zip(customer_zip, fiscal_config)
            if not resolved_customer_zip:
                return {"success": False, "error": "Codigo postal del receptor o lugar de expedicion no configurado"}

            if fiscal_config.get("facturapi_enabled") and fiscal_config.get("facturapi_api_key"):
                return await self.generate_cfdi_via_facturapi(
                    sale_id, customer_rfc, customer_name, customer_regime,
                    uso_cfdi, None, resolved_customer_zip, forma_pago,
                )

            # CFDI-021: Reserve folio atomically BEFORE building XML so that no
            # two concurrent requests can produce the same folio number.
            reserved_folio = await self._reserve_folio()
            fiscal_config_with_folio = {**fiscal_config, "folio_actual": reserved_folio}

            customer_data = {
                "rfc": customer_rfc.upper(),
                "nombre": customer_name or "PUBLICO EN GENERAL",
                "codigo_postal": resolved_customer_zip,
                "regimen_fiscal": customer_regime,
                "uso_cfdi": uso_cfdi,
            }

            from modules.fiscal.cfdi_builder import CFDIBuilder
            builder = CFDIBuilder(fiscal_config_with_folio)
            xml_unsigned = builder.build(sale_data, customer_data)

            from modules.fiscal.signature import sign_cfdi_xml
            xml_signed = sign_cfdi_xml(xml_unsigned, fiscal_config_with_folio)

            from modules.fiscal.pac_connector import create_pac_connector
            pac = create_pac_connector(fiscal_config_with_folio)
            timbrado_result = await pac.timbrar_cfdi(xml_signed)

            if not timbrado_result.get("success"):
                return {"success": False, "error": timbrado_result.get("error", "Unknown")}

            uuid = timbrado_result["uuid"]
            xml_timbrado = timbrado_result["xml_timbrado"]

            cfdi_record = {
                "sale_id": sale_id,
                "uuid": uuid,
                "folio": reserved_folio,
                "serie": fiscal_config.get("serie_factura", "F"),
                "rfc_receptor": customer_rfc,
                "nombre_receptor": customer_data["nombre"],
                "regimen_receptor": customer_regime,
                "uso_cfdi": uso_cfdi,
                "xml_original": xml_signed,
                "xml_timbrado": xml_timbrado,
                "fecha_emision": sale_data.get("timestamp"),
                "fecha_timbrado": timbrado_result.get("fecha_timbrado"),
                "total": sale_data.get("total"),
                "subtotal": sale_data.get("subtotal"),
                "impuestos": sale_data.get("tax"),
            }

            cfdi_id = await self._save_cfdi(cfdi_record)
            xml_path = await self._save_xml_file(uuid, xml_timbrado)
            await self._promote_sale_to_serie_a(sale_id, uuid, sale_data)

            return {"success": True, "cfdi_id": cfdi_id, "uuid": uuid, "xml_path": xml_path, "xml_timbrado": xml_timbrado}
        except Exception as e:
            logger.error(f"Error generando CFDI para venta {sale_id}: {e}", exc_info=True)
            return {"success": False, "error": "Error interno al generar CFDI"}

    _CFDI_ALLOWED_COLS = frozenset({
        "sale_id", "uuid", "folio", "serie", "fecha", "rfc_emisor", "rfc_receptor",
        "razon_social_emisor", "razon_social_receptor", "subtotal", "impuestos", "total",
        "moneda", "metodo_pago", "forma_pago", "uso_cfdi", "tipo_comprobante",
        "regimen_fiscal", "lugar_expedicion", "xml_path", "xml_timbrado", "xml_original",
        "emitter_rfc", "receiver_rfc", "status", "estado", "created_at", "updated_at",
        "nombre_receptor", "regimen_receptor", "facturapi_id",
        "fecha_emision", "fecha_timbrado", "fecha_cancelacion", "motivo_cancelacion",
        "cfdi_relacionado", "tipo_relacion",
    })

    async def _save_cfdi(self, cfdi_data: Dict[str, Any]) -> int:
        cols = [c for c in cfdi_data.keys() if c in self._CFDI_ALLOWED_COLS]
        if not cols:
            raise ValueError("No valid columns in cfdi_data")
        filtered_data = {c: cfdi_data[c] for c in cols}
        col_names = ", ".join(cols)
        placeholders = ", ".join([f":{c}" for c in cols])
        sql = f"INSERT INTO cfdis ({col_names}) VALUES ({placeholders}) RETURNING id"
        row = await self.db.fetchrow(sql, filtered_data)
        return row["id"] if row else 0

    async def _save_xml_file(self, uuid: str, xml_content: str) -> str:
        import re
        from modules.fiscal.utils import DATA_DIR

        # Validate UUID format to prevent path traversal
        if not re.match(r'^[a-fA-F0-9\-]{32,36}$', uuid):
            raise ValueError(f"Invalid UUID format for file save: {uuid}")

        cfdi_dir = Path(DATA_DIR) / "cfdis"
        await asyncio.to_thread(cfdi_dir.mkdir, exist_ok=True, parents=True)
        xml_path = (cfdi_dir / f"{uuid}.xml").resolve()

        # Ensure resolved path is still under cfdi_dir
        if not str(xml_path).startswith(str(cfdi_dir.resolve())):
            raise ValueError("Path traversal detected in UUID")

        async with aiofiles.open(xml_path, "w", encoding="utf-8") as f:
            await f.write(xml_content)
        return str(xml_path)

    async def _promote_sale_to_serie_a(self, sale_id: int, cfdi_uuid: str, sale_data: Dict[str, Any]):
        from datetime import datetime

        try:
            sale_info = await self.db.fetchrow(
                "SELECT serie, timestamp FROM sales WHERE id = :sid", {"sid": sale_id}
            )
            if not sale_info:
                return

            current_serie = sale_info.get("serie", "B")
            sale_date = sale_info.get("timestamp", "")

            if current_serie != "B":
                await self.db.execute(
                    "UPDATE sales SET cfdi_uuid = :uuid, rfc_used = :rfc WHERE id = :sid",
                    {"uuid": cfdi_uuid, "rfc": sale_data.get("customer_rfc", ""), "sid": sale_id},
                )
                return

            await self.db.execute(
                "UPDATE sales SET serie = 'A', cfdi_uuid = :uuid, rfc_used = :rfc, updated_at = :ts WHERE id = :sid",
                {
                    "uuid": cfdi_uuid,
                    "rfc": sale_data.get("customer_rfc", ""),
                    "ts": datetime.now().isoformat(),
                    "sid": sale_id,
                },
            )

            items = sale_data.get("items", [])
            if items:
                try:
                    for item in items:
                        product_id = item.get("product_id")
                        quantity = Decimal(str(item.get("quantity", 0)))
                        if product_id and quantity > 0:
                            await self.db.execute(
                                "UPDATE products SET shadow_stock = COALESCE(shadow_stock, 0) + :qty WHERE id = :pid",
                                {"qty": quantity, "pid": product_id},
                            )
                except Exception as e:
                    logger.warning(f"Shadow stock adjustment failed: {e}")

            try:
                await self.db.execute(
                    "INSERT INTO shadow_movements (product_id, movement_type, quantity, source, notes, created_at) "
                    "VALUES (0, 'SALE_PROMOTION', 0, :src, :notes, :ts)",
                    {
                        "src": f"Sale {sale_id} promoted B->A",
                        "notes": f"CFDI {cfdi_uuid}, Original date: {sale_date}",
                        "ts": datetime.now().isoformat(),
                    },
                )
            except Exception as e:
                logger.debug(f"Shadow movement insert failed (non-critical): {e}")
        except Exception as e:
            logger.error(f"Error promoting sale {sale_id} to Serie A: {e}")

    async def get_cfdi_by_sale(self, sale_id: int) -> Optional[Dict[str, Any]]:
        return await self.db.fetchrow(
            "SELECT * FROM cfdis WHERE sale_id = :sid", {"sid": sale_id}
        )

    async def cancel_cfdi(self, uuid: str, motivo: str = "02", folio_sustitucion: Optional[str] = None) -> Dict[str, Any]:
        try:
            fiscal_config = await self._get_fiscal_config()
            from modules.fiscal.pac_connector import create_pac_connector

            pac = create_pac_connector(fiscal_config)
            result = await pac.cancelar_cfdi(uuid, motivo, folio_sustitucion)

            if result.get("success"):
                await self.db.execute(
                    "UPDATE cfdis SET estado = 'cancelado', motivo_cancelacion = :motivo, "
                    "fecha_cancelacion = :fecha WHERE uuid = :uuid",
                    {"motivo": motivo, "fecha": result.get("fecha_cancelacion"), "uuid": uuid},
                )
            return result
        except Exception as e:
            logger.error(f"Error cancelando CFDI {uuid} via PAC: {e}", exc_info=True)
            return {"success": False, "error": "Error interno al cancelar CFDI"}

    async def generate_credit_note(
        self,
        original_uuid: str,
        customer_rfc: str,
        customer_name: Optional[str] = None,
        customer_regime: str = "616",
        uso_cfdi: str = "G02",
        items: Optional[list] = None,
        descripcion: str = "Nota de crédito por devolución",
    ) -> Dict[str, Any]:
        try:
            original = await self.db.fetchrow(
                "SELECT * FROM cfdis WHERE uuid = :uuid", {"uuid": original_uuid}
            )
            if not original:
                return {"success": False, "error": f"CFDI original {original_uuid} no encontrado"}

            original_sale_id = original.get("sale_id")
            if isinstance(original_sale_id, int) and original_sale_id > 0:
                await self._resolve_branch_id_for_sale(original_sale_id)
            fiscal_config = await self._get_fiscal_config()
            resolved_customer_zip = self._resolve_customer_zip(original.get("lugar_expedicion"), fiscal_config)
            if not resolved_customer_zip:
                return {"success": False, "error": "Codigo postal del receptor o lugar de expedicion no configurado"}

            if items is None and original_sale_id:
                sale_data = await self._get_sale_details(original_sale_id)
                items = sale_data.get("items", []) if sale_data else []

            if not items:
                return {"success": False, "error": "No hay productos para la nota de crédito"}

            # Use item subtotals (pre-tax) if available, otherwise back-calculate from total
            raw_subtotal = Decimal("0")
            for item in items:
                if item.get("subtotal") is not None:
                    raw_subtotal += Decimal(str(item["subtotal"]))
                else:
                    # item["total"] likely includes tax; back-calculate pre-tax amount
                    item_total = Decimal(str(item.get("total", 0)))
                    raw_subtotal += (item_total / (1 + IVA_RATE)).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
            subtotal = raw_subtotal
            tax = (subtotal * IVA_RATE).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            total = subtotal + tax

            # CFDI-021: Reserve folio atomically BEFORE building XML.
            reserved_folio = await self._reserve_folio()
            fiscal_config_with_folio = {**fiscal_config, "folio_actual": reserved_folio}

            credit_note_data = {
                "tipo_comprobante": "E",
                "subtotal": subtotal,
                "tax": tax,
                "total": total,
                "items": items,
                "cfdi_relacionado": original_uuid,
                "tipo_relacion": "01",
                "descripcion_nota": descripcion,
            }
            customer_data = {
                "rfc": customer_rfc.upper(),
                "nombre": customer_name or original.get("nombre_receptor", "PUBLICO EN GENERAL"),
                "codigo_postal": resolved_customer_zip,
                "regimen_fiscal": customer_regime,
                "uso_cfdi": uso_cfdi,
            }

            from modules.fiscal.cfdi_builder import CFDIBuilder
            builder = CFDIBuilder(fiscal_config_with_folio)
            xml_unsigned = builder.build_credit_note(credit_note_data, customer_data)

            from modules.fiscal.signature import sign_cfdi_xml
            xml_signed = sign_cfdi_xml(xml_unsigned, fiscal_config_with_folio)

            from modules.fiscal.pac_connector import create_pac_connector
            pac = create_pac_connector(fiscal_config_with_folio)
            timbrado_result = await pac.timbrar_cfdi(xml_signed)

            if not timbrado_result.get("success"):
                return {"success": False, "error": timbrado_result.get("error", "Unknown")}

            uuid = timbrado_result["uuid"]
            xml_timbrado = timbrado_result["xml_timbrado"]

            cfdi_record = {
                "sale_id": None,
                "uuid": uuid,
                "folio": reserved_folio,
                "serie": fiscal_config.get("serie_nota_credito", "NC"),
                "tipo_comprobante": "E",
                "rfc_receptor": customer_rfc,
                "nombre_receptor": customer_data["nombre"],
                "regimen_receptor": customer_regime,
                "uso_cfdi": uso_cfdi,
                "xml_original": xml_signed,
                "xml_timbrado": xml_timbrado,
                "total": total,
                "subtotal": subtotal,
                "impuestos": tax,
                "cfdi_relacionado": original_uuid,
                "tipo_relacion": "01",
            }

            cfdi_id = await self._save_cfdi(cfdi_record)

            xml_path = await self._save_xml_file(uuid, xml_timbrado)

            return {
                "success": True,
                "cfdi_id": cfdi_id,
                "uuid": uuid,
                "xml_path": xml_path,
                "total": total,
                "original_uuid": original_uuid,
            }
        except Exception as e:
            logger.error(f"Error generando nota de crédito para CFDI {original_uuid}: {e}", exc_info=True)
            return {"success": False, "error": "Error interno al generar nota de crédito"}
