"""
📄 Facturapi Connector - Integración Completa
Traducido de la documentación oficial PHP → Python

Facturapi usa PCCFDI (antes PAC) autorizados por el SAT.

Características Soportadas:
- CFDI 4.0 (Ingreso, Egreso, Pago, Nómina, Traslado)
- E-receipts (recibos digitales facturables)
- Autofactura (portal de autoservicio)
- Factura global
- Multi RFC (Organizaciones)
- Cancelaciones
- Complementos y Addendas
- Borradores de facturas
- Facturación asíncrona
- Personalización de PDF

Instalación:
    pip install requests

Configuración en .env:
    FACTURAPI_KEY=sk_test_xxxxxxxxxxxxx
    FACTURAPI_MODE=test  # o "live" para producción

Uso:
    from src.services.fiscal.facturapi_connector import Facturapi
    
    facturapi = Facturapi("sk_test_xxx")
    invoice = facturapi.invoices.create({...})
"""
from typing import Any, Dict, List, Optional
from datetime import datetime
from decimal import Decimal
import json
import logging
import os

logger = logging.getLogger("FACTURAPI")

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    logger.warning("requests no instalado. Ejecutar: pip install requests")

class FacturapiResource:
    """Clase base para recursos de la API."""
    
    def __init__(self, client: 'Facturapi', resource_name: str):
        self.client = client
        self.resource_name = resource_name
    
    def _request(self, method: str, endpoint: str = '', data: dict = None, 
                 params: dict = None) -> dict:
        return self.client._request(method, f"{self.resource_name}/{endpoint}".rstrip('/'), 
                                    data, params)

class Invoices(FacturapiResource):
    """
    Gestión de Facturas (CFDI).
    
    Tipos soportados:
    - I: Ingreso (factura de venta)
    - E: Egreso (nota de crédito)
    - P: Pago (complemento de pago / REP)
    - N: Nómina
    - T: Traslado
    """
    
    def __init__(self, client: 'Facturapi'):
        super().__init__(client, 'invoices')
    
    def create(self, data: Dict[str, Any], options: Dict[str, Any] = None) -> dict:
        """
        Crea y timbra una factura.
        
        Ejemplos de uso:
        
        # Factura con pago de contado (PUE)
        invoice = facturapi.invoices.create({
            "customer": {
                "legal_name": "Dunder Mifflin",
                "email": "email@example.com",
                "tax_id": "ABC101010111",
                "tax_system": "601",
                "address": {"zip": "85900"}
            },
            "items": [{
                "quantity": 2,
                "product": {
                    "description": "Ukelele",
                    "product_key": "60131324",
                    "price": 345.60,
                    "taxes": [{"type": "IVA", "rate": 0.16}]
                }
            }],
            "payment_form": "28"  # Tarjeta de débito
        })
        
        # Factura a crédito (PPD)
        invoice = facturapi.invoices.create({
            "customer": {...},
            "items": [...],
            "payment_form": "99",
            "payment_method": "PPD",
            "conditions": "Fecha límite de pago: 2026-02-01"
        })
        
        # Factura asíncrona
        invoice = facturapi.invoices.create({...}, {"async": True})
        """
        params = {}
        if options and options.get('async'):
            params['async'] = 'true'
        
        return self._request('POST', '', data, params)
    
    def create_income(self, customer: dict, items: list, payment_form: str,
                      payment_method: str = 'PUE', **kwargs) -> dict:
        """
        Crea factura de Ingreso (tipo I) - Atajo conveniente.
        
        Args:
            customer: Datos del cliente
            items: Lista de productos/servicios
            payment_form: Forma de pago SAT (01=Efectivo, 28=Tarjeta débito, etc.)
            payment_method: PUE (contado) o PPD (crédito)
        """
        data = {
            "type": "I",
            "customer": customer,
            "items": items,
            "payment_form": payment_form,
            "payment_method": payment_method,
            **kwargs
        }
        return self.create(data)
    
    def create_credit_note(self, customer: dict, items: list, 
                           related_uuid: str, payment_form: str = "28") -> dict:
        """
        Crea Nota de Crédito (tipo E).
        
        Ejemplo - Descuento sobre factura previa:
        invoice = facturapi.invoices.create_credit_note(
            customer={...},
            items=[{
                "product": {
                    "description": "Descuento",
                    "price": 400,
                    "taxes": [{"type": "IVA", "rate": 0.16}]
                }
            }],
            related_uuid="39c85a3f-275b-4341-b259-e8971d9f8a94",
            payment_form="28"
        )
        """
        data = {
            "type": "E",
            "customer": customer,
            "items": items,
            "payment_form": payment_form,
            "related_documents": [{
                "relationship": "01",  # Nota de crédito
                "documents": [related_uuid] if isinstance(related_uuid, str) else related_uuid
            }]
        }
        return self.create(data)
    
    def create_payment(self, customer: dict, payments: list) -> dict:
        """
        Crea Complemento de Pago / REP (tipo P).
        
        Ejemplo - Pago total de factura PPD:
        invoice = facturapi.invoices.create_payment(
            customer={...},
            payments=[{
                "payment_form": "28",
                "related_documents": [{
                    "uuid": "39c85a3f-275b-...",
                    "amount": 345.60,
                    "installment": 1,
                    "last_balance": 345.60,
                    "taxes": [{"base": 297.93, "type": "IVA", "rate": 0.16}]
                }]
            }]
        )
        
        Ejemplo - Pago en parcialidades:
        invoice = facturapi.invoices.create_payment(
            customer={...},
            payments=[{
                "payment_form": "28",
                "related_documents": [{
                    "uuid": "39c85a3f-...",
                    "amount": 100,           # Monto de esta parcialidad
                    "installment": 2,        # Número de parcialidad
                    "last_balance": 245.60,  # Saldo anterior
                    "taxes": [{"base": 86.21, "type": "IVA", "rate": 0.16}]
                }]
            }]
        )
        """
        data = {
            "type": "P",
            "customer": customer,
            "complements": [{
                "type": "pago",
                "data": payments
            }]
        }
        return self.create(data)
    
    def create_payroll(self, employee: dict, payroll_data: dict, 
                       folio_number: int = None, series: str = "N") -> dict:
        """
        Crea Recibo de Nómina (tipo N).
        
        employee: Datos del empleado (customer)
        payroll_data: Datos del complemento de nómina
        """
        data = {
            "type": "N",
            "series": series,
            "customer": employee,
            "complements": [{
                "type": "nomina",
                "data": payroll_data
            }]
        }
        if folio_number:
            data["folio_number"] = folio_number
        
        return self.create(data)
    
    def create_substitute(self, customer: dict, items: list, 
                          canceled_uuid: str, payment_form: str) -> dict:
        """
        Crea factura que sustituye a una cancelada (relación 04).
        """
        data = {
            "type": "I",
            "customer": customer,
            "items": items,
            "payment_form": payment_form,
            "related_documents": [{
                "relationship": "04",  # Sustitución
                "documents": [canceled_uuid]
            }]
        }
        return self.create(data)
    
    def create_draft(self, data: Dict[str, Any]) -> dict:
        """
        Crea un borrador de factura (sin timbrar).
        
        Los borradores pueden editarse antes de timbrar.
        """
        data["status"] = "draft"
        return self.create(data)
    
    def update_draft(self, invoice_id: str, data: Dict[str, Any]) -> dict:
        """Edita un borrador de factura."""
        return self._request('PUT', invoice_id, data)
    
    def stamp_draft(self, invoice_id: str) -> dict:
        """Timbra un borrador (lo convierte en factura válida)."""
        return self._request('POST', f"{invoice_id}/stamp")
    
    def get(self, invoice_id: str) -> dict:
        """Obtiene una factura por ID."""
        return self._request('GET', invoice_id)
    
    def list(self, params: dict = None) -> dict:
        """Lista facturas con filtros opcionales."""
        return self._request('GET', '', params=params)
    
    def cancel(self, invoice_id: str, motive: str = "02", 
               substitution: str = None) -> dict:
        """
        Cancela una factura.
        
        Motivos de cancelación:
        - 01: Con relación (requiere substitution)
        - 02: Sin relación (más común)
        - 03: No se llevó a cabo la operación
        - 04: Operación nominativa
        """
        # Facturapi expects motive as query parameter for DELETE
        params = {"motive": motive}
        if motive == "01" and substitution:
            params["substitution"] = substitution
        
        return self._request('DELETE', invoice_id, params=params)
    
    def download_pdf(self, invoice_id: str) -> bytes:
        """Descarga el PDF de la factura."""
        url = f"{self.client.base_url}/invoices/{invoice_id}/pdf"
        response = requests.get(url, headers=self.client._headers(), timeout=60)
        if response.status_code >= 400:
            raise Exception(f"Error {response.status_code}: {response.text}")
        return response.content
    
    def download_xml(self, invoice_id: str) -> str:
        """Descarga el XML de la factura."""
        url = f"{self.client.base_url}/invoices/{invoice_id}/xml"
        response = requests.get(url, headers=self.client._headers(), timeout=60)
        if response.status_code >= 400:
            raise Exception(f"Error {response.status_code}: {response.text}")
        return response.text
    
    def send_by_email(self, invoice_id: str, email: str = None) -> dict:
        """Envía la factura por correo."""
        data = {}
        if email:
            data["email"] = email
        return self._request('POST', f"{invoice_id}/email", data)
    
    def copy_to_draft(self, invoice_id: str) -> dict:
        """
        Crea una copia en borrador de la factura especificada.
        
        Útil para corregir facturas canceladas.
        """
        return self._request('POST', f"{invoice_id}/copy")
    
    def preview_pdf(self, data: Dict[str, Any]) -> bytes:
        """
        Genera vista previa en PDF sin timbrar ni guardar.
        
        Útil para mostrar al usuario cómo quedará la factura.
        """
        url = f"{self.client.base_url}/invoices/preview"
        response = requests.post(
            url, 
            headers=self.client._headers(), 
            json=data,
            timeout=60
        )
        return response.content
    
    def download_zip(self, invoice_id: str) -> bytes:
        """Descarga ZIP con PDF y XML de la factura."""
        url = f"{self.client.base_url}/invoices/{invoice_id}/zip"
        response = requests.get(url, headers=self.client._headers(), timeout=60)
        if response.status_code >= 400:
            raise Exception(f"Error {response.status_code}: {response.text}")
        return response.content
    
    def download_cancellation_receipt(self, invoice_id: str, 
                                       format: str = "xml") -> bytes:
        """
        Descarga acuse de cancelación.
        
        Args:
            invoice_id: ID de la factura cancelada
            format: "xml" o "pdf"
        """
        url = f"{self.client.base_url}/invoices/{invoice_id}/cancellation_receipt/{format}"
        response = requests.get(url, headers=self.client._headers(), timeout=60)
        return response.content
    
    def update_status(self, invoice_id: str) -> dict:
        """
        Consulta el status de la factura en el SAT y actualiza el objeto.
        
        Útil para verificar estado de cancelación.
        """
        return self._request('PUT', f"{invoice_id}/status")

class Receipts(FacturapiResource):
    """
    Gestión de E-Receipts (Recibos Digitales).
    
    Los e-receipts son tickets que pueden convertirse en factura después.
    Incluyen portal de autofactura para que el cliente complete sus datos.
    """
    
    def __init__(self, client: 'Facturapi'):
        super().__init__(client, 'receipts')
    
    def create(self, data: Dict[str, Any]) -> dict:
        """
        Crea un e-receipt.
        
        Ejemplo:
        receipt = facturapi.receipts.create({
            "folio_number": 1234,
            "payment_form": "03",
            "items": [{
                "description": "Ukelele",
                "product_key": "60131324",
                "price": 345.60,
                "sku": "ABC1234"
            }]
        })
        
        # El receipt tiene self_invoice_url para autofactura
        print(receipt["self_invoice_url"])
        """
        return self._request('POST', '', data)
    
    def get(self, receipt_id: str) -> dict:
        """Obtiene un recibo por ID."""
        return self._request('GET', receipt_id)
    
    def list(self, params: dict = None) -> dict:
        """Lista recibos."""
        return self._request('GET', '', params=params)
    
    def invoice(self, receipt_id: str, invoice_data: Dict[str, Any]) -> dict:
        """
        Convierte un e-receipt en factura.
        
        Ejemplo:
        invoice = facturapi.receipts.invoice(receipt_id, {
            "customer": {
                "legal_name": "Roger Watters",
                "tax_id": "ROWA121212A11",
                "email": "roger@email.com"
            },
            "folio_number": 914,
            "series": "F"
        })
        """
        return self._request('POST', f"{receipt_id}/invoice", invoice_data)
    
    def assign_customer(self, receipt_id: str, customer_id: str) -> dict:
        """Asigna un cliente existente a un recibo."""
        return self._request('PUT', receipt_id, {"customer": customer_id})
    
    def cancel(self, receipt_id: str) -> dict:
        """Cancela un recibo (solo si no ha sido facturado)."""
        return self._request('DELETE', receipt_id)
    
    def create_global_invoice(self, receipt_ids: list, 
                               periodicity: str = "month",
                               month: str = None, year: str = None) -> dict:
        """
        Crea factura global con múltiples e-receipts no facturados.
        """
        data = {
            "periodicity": periodicity,
            "receipts": receipt_ids
        }
        if month:
            data["month"] = month
        if year:
            data["year"] = year
        
        return self.client._request('POST', 'invoices', data)

class Customers(FacturapiResource):
    """
    Gestión de Clientes.
    
    Soporta clientes nacionales y extranjeros.
    Incluye enlaces de edición para autofactura.
    """
    
    def __init__(self, client: 'Facturapi'):
        super().__init__(client, 'customers')
    
    def create(self, data: Dict[str, Any], options: Dict[str, Any] = None) -> dict:
        """
        Crea un cliente.
        
        Ejemplos:
        
        # Cliente nacional
        customer = facturapi.customers.create({
            "legal_name": "Dunder Mifflin",
            "tax_id": "ABC101010111",
            "tax_system": "601",
            "email": "email@example.com",
            "address": {"zip": "85900"}
        })
        
        # Cliente extranjero
        customer = facturapi.customers.create({
            "legal_name": "Vättenfall, A.B.",
            "tax_id": "198912171234",
            "address": {"country": "SWE", "zip": "17123", "city": "Stockholm"}
        })
        
        # Cliente con enlace de edición (autofactura)
        customer = facturapi.customers.create(
            {"email": "cliente@ejemplo.com"},
            {"createEditLink": True}
        )
        # El cliente tendrá edit_link para completar sus datos
        """
        params = {}
        if options and options.get('createEditLink'):
            params['createEditLink'] = 'true'
        
        return self._request('POST', '', data, params)
    
    def retrieve(self, customer_id: str) -> dict:
        """Obtiene un cliente por ID (alias de get)."""
        return self._request('GET', customer_id)
    
    def get(self, customer_id: str) -> dict:
        """Obtiene un cliente por ID."""
        return self._request('GET', customer_id)
    
    def list(self, params: dict = None) -> dict:
        """Lista clientes."""
        return self._request('GET', '', params=params)
    
    def search_by_rfc(self, rfc: str) -> dict:
        """Busca cliente por RFC."""
        result = self.list({"tax_id": rfc})
        if result.get('success') and result.get('data', {}).get('data'):
            return {'success': True, 'data': result['data']['data'][0]}
        return {'success': False, 'error': 'Cliente no encontrado'}
    
    def update(self, customer_id: str, data: Dict[str, Any] = None, 
               options: Dict[str, Any] = None) -> dict:
        """
        Actualiza un cliente.
        
        Ejemplo - Renovar enlace de edición:
        customer = facturapi.customers.update(
            "customer_id", 
            {}, 
            {"createEditLink": True}
        )
        """
        params = {}
        if options and options.get('createEditLink'):
            params['createEditLink'] = 'true'
        
        return self._request('PUT', customer_id, data or {}, params)
    
    def send_edit_link_by_email(self, customer_id: str, email: str = None) -> dict:
        """
        Envía enlace de edición de datos fiscales por correo.
        
        Si no se especifica email, usa el del cliente.
        """
        data = {}
        if email:
            data["email"] = email
        return self._request('POST', f"{customer_id}/edit-link/email", data)
    
    def delete(self, customer_id: str) -> dict:
        """Elimina un cliente."""
        return self._request('DELETE', customer_id)

class Products(FacturapiResource):
    """
    Gestión de Productos.
    
    Soporta productos con IVA incluido/no incluido, tasa 0, exento.
    """
    
    def __init__(self, client: 'Facturapi'):
        super().__init__(client, 'products')
    
    def create(self, data: Dict[str, Any]) -> dict:
        """
        Crea un producto.
        
        Ejemplos:
        
        # Producto con IVA 16% incluido (default)
        product = facturapi.products.create({
            "description": "Ukelele",
            "product_key": "4319150114",
            "price": 345.60,  # Precio CON IVA
            "sku": "ABC1234"
        })
        # Precio unitario: 297.93, IVA: 47.67, Total: 345.60
        
        # Producto con precio ANTES de impuestos
        product = facturapi.products.create({
            "description": "Ukelele",
            "product_key": "4319150114",
            "price": 345.60,  # Precio SIN IVA
            "tax_included": False,
            "taxes": [{"type": "IVA", "rate": 0.16}]
        })
        # Precio unitario: 345.60, IVA: 55.30, Total: 400.90
        
        # Producto IVA tasa 0
        product = facturapi.products.create({
            "description": "Alimento básico",
            "product_key": "50221304",
            "price": 100.00,
            "tax_included": False,
            "taxes": [{"type": "IVA", "rate": 0}]
        })
        
        # Producto IVA exento
        product = facturapi.products.create({
            "description": "Servicio médico",
            "product_key": "85121800",
            "price": 500.00,
            "tax_included": False,
            "taxes": [{"type": "IVA", "factor": "Exento", "rate": 0}]
        })
        """
        return self._request('POST', '', data)
    
    def create_with_tax_included(self, description: str, product_key: str,
                                  price: float, sku: str = None,
                                  unit_key: str = "H87", 
                                  iva_rate: float = 0.16) -> dict:
        """
        Atajo: Crea producto con IVA incluido en precio.
        """
        data = {
            "description": description,
            "product_key": product_key,
            "unit_key": unit_key,
            "price": price,
            "tax_included": True,
            "taxes": [{"type": "IVA", "rate": iva_rate}]
        }
        if sku:
            data["sku"] = sku
        return self.create(data)
    
    def create_without_tax(self, description: str, product_key: str,
                           price: float, sku: str = None,
                           unit_key: str = "H87",
                           iva_rate: float = 0.16) -> dict:
        """
        Atajo: Crea producto con precio ANTES de IVA.
        """
        data = {
            "description": description,
            "product_key": product_key,
            "unit_key": unit_key,
            "price": price,
            "tax_included": False,
            "taxes": [{"type": "IVA", "rate": iva_rate}]
        }
        if sku:
            data["sku"] = sku
        return self.create(data)
    
    def create_exempt(self, description: str, product_key: str,
                      price: float, sku: str = None,
                      unit_key: str = "H87") -> dict:
        """
        Atajo: Crea producto con IVA exento.
        """
        data = {
            "description": description,
            "product_key": product_key,
            "unit_key": unit_key,
            "price": price,
            "tax_included": False,
            "taxes": [{"type": "IVA", "factor": "Exento", "rate": 0}]
        }
        if sku:
            data["sku"] = sku
        return self.create(data)
    
    def get(self, product_id: str) -> dict:
        return self._request('GET', product_id)
    
    def list(self, params: dict = None) -> dict:
        return self._request('GET', '', params=params)
    
    def search(self, query: str) -> dict:
        """Busca productos por descripción o SKU."""
        return self.list({"q": query})
    
    def update(self, product_id: str, data: Dict[str, Any]) -> dict:
        return self._request('PUT', product_id, data)
    
    def delete(self, product_id: str) -> dict:
        return self._request('DELETE', product_id)

class Organizations(FacturapiResource):
    """
    Gestión de Organizaciones (Multi-RFC).
    
    Requiere User Key en lugar de API Key.
    """
    
    def __init__(self, client: 'Facturapi'):
        super().__init__(client, 'organizations')
    
    def create(self, data: Dict[str, Any]) -> dict:
        """
        Crea una nueva organización emisora.
        
        Ejemplo:
        org = facturapi.organizations.create({"name": "Mi Empresa SA"})
        """
        return self._request('POST', '', data)
    
    def get(self, org_id: str = None) -> dict:
        if org_id:
            return self._request('GET', org_id)
        return self._request('GET', '')
    
    def update_legal(self, org_id: str, data: Dict[str, Any]) -> dict:
        """Actualiza datos fiscales de la organización."""
        return self._request('PUT', f"{org_id}/legal", data)
    
    def upload_certificates(self, org_id: str, cer_base64: str, 
                            key_base64: str, password: str) -> dict:
        """Sube certificados CSD."""
        data = {
            "cer": cer_base64,
            "key": key_base64,
            "password": password
        }
        return self._request('PUT', f"{org_id}/certificates", data)

class Tools(FacturapiResource):
    """Herramientas de validación."""
    
    def __init__(self, client: 'Facturapi'):
        super().__init__(client, 'tools')
    
    def validate_rfc(self, rfc: str) -> dict:
        """Valida un RFC con el SAT."""
        return self._request('GET', 'tax_id_validation', params={"tax_id": rfc})

class Catalogs(FacturapiResource):
    """Catálogos del SAT."""
    
    def __init__(self, client: 'Facturapi'):
        super().__init__(client, 'catalogs')
    
    def get(self, catalog_type: str, params: dict = None) -> dict:
        """
        Obtiene un catálogo del SAT.
        
        Tipos: product_keys, unit_keys, tax_systems, payment_forms, etc.
        """
        return self._request('GET', catalog_type, params=params)
    
    def product_keys(self, query: str = None) -> dict:
        """Busca claves de producto SAT."""
        params = {"q": query} if query else None
        return self.get('product_keys', params)
    
    def unit_keys(self) -> dict:
        """Lista claves de unidad SAT."""
        return self.get('unit_keys')

class Retentions(FacturapiResource):
    """
    Gestión de Retenciones (CFDI de Retención).
    
    Para pagos a residentes en el extranjero, dividendos, etc.
    """
    
    def __init__(self, client: 'Facturapi'):
        super().__init__(client, 'retentions')
    
    def create(self, data: Dict[str, Any]) -> dict:
        """
        Crea una retención.
        
        Ejemplo:
        retention = facturapi.retentions.create({
            "customer": {...},
            "cve_retenc": "01",  # Clave de retención SAT
            "periodo": {...},
            "totales": {...}
        })
        """
        return self._request('POST', '', data)
    
    def get(self, retention_id: str) -> dict:
        return self._request('GET', retention_id)
    
    def list(self, params: dict = None) -> dict:
        return self._request('GET', '', params=params)
    
    def cancel(self, retention_id: str) -> dict:
        """Cancela una retención."""
        return self._request('DELETE', retention_id)
    
    def download_pdf(self, retention_id: str) -> bytes:
        """Descarga el PDF de la retención."""
        url = f"{self.client.base_url}/retentions/{retention_id}/pdf"
        response = requests.get(url, headers=self.client._headers(), timeout=60)
        return response.content
    
    def download_xml(self, retention_id: str) -> str:
        """Descarga el XML de la retención."""
        url = f"{self.client.base_url}/retentions/{retention_id}/xml"
        response = requests.get(url, headers=self.client._headers(), timeout=60)
        return response.text
    
    def send_by_email(self, retention_id: str, email: str = None) -> dict:
        """Envía la retención por correo."""
        data = {"email": email} if email else {}
        return self._request('POST', f"{retention_id}/email", data)

class Webhooks(FacturapiResource):
    """
    Gestión de Webhooks.
    
    Recibe notificaciones de eventos asíncronos:
    - Factura global creada
    - Estatus de factura actualizado
    - Autofactura completada
    - Estatus de cancelación actualizado
    """
    
    def __init__(self, client: 'Facturapi'):
        super().__init__(client, 'webhooks')
    
    def create(self, url: str, events: List[str] = None) -> dict:
        """
        Crea un webhook.
        
        Eventos disponibles:
        - invoice.global_created
        - invoice.status_updated
        - invoice.created_from_dashboard
        - invoice.cancellation_status_updated
        - receipt.self_invoice_complete
        - receipt.status_updated
        
        Ejemplo:
        webhook = facturapi.webhooks.create(
            url="https://miapp.com/webhook",
            events=["invoice.status_updated", "receipt.self_invoice_complete"]
        )
        """
        data = {"url": url}
        if events:
            data["enabled_events"] = events
        return self._request('POST', '', data)
    
    def get(self, webhook_id: str) -> dict:
        return self._request('GET', webhook_id)
    
    def list(self) -> dict:
        return self._request('GET', '')
    
    def update(self, webhook_id: str, data: Dict[str, Any]) -> dict:
        return self._request('PUT', webhook_id, data)
    
    def delete(self, webhook_id: str) -> dict:
        return self._request('DELETE', webhook_id)
    
    def validate_signature(self, payload: str, signature: str, 
                           webhook_secret: str) -> bool:
        """
        Valida la firma de un evento de webhook.
        
        Usar para verificar que el evento viene de Facturapi.
        """
        import hashlib
        import hmac
        
        expected = hmac.new(
            webhook_secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected, signature)

class Facturapi:
    """
    Cliente principal de Facturapi.
    
    Recursos disponibles:
    - invoices: Facturas (CFDI)
    - receipts: E-Receipts (recibos digitales)
    - customers: Clientes
    - products: Productos
    - organizations: Organizaciones (Multi-RFC)
    - retentions: Retenciones
    - webhooks: Webhooks
    - tools: Herramientas (validación RFC, etc.)
    - catalogs: Catálogos SAT
    
    Uso:
        facturapi = Facturapi("sk_test_xxx")
        invoice = facturapi.invoices.create({...})
    """
    
    BASE_URL = "https://www.facturapi.io/v2"
    
    def __init__(self, api_key: str = None):
        """
        Inicializa el cliente.
        
        Args:
            api_key: API Key (sk_test_xxx o sk_live_xxx)
                     Si no se provee, lee de FACTURAPI_KEY
        """
        if not HAS_REQUESTS:
            raise ImportError("Se requiere 'requests'. Ejecutar: pip install requests")
        
        self.api_key = api_key or os.getenv('FACTURAPI_KEY')
        
        if not self.api_key:
            raise ValueError(
                "API Key requerida. Configurar FACTURAPI_KEY o pasar como parámetro."
            )
        
        self.base_url = self.BASE_URL
        self.mode = 'test' if 'test' in self.api_key else 'live'
        
        # Recursos
        self.invoices = Invoices(self)
        self.receipts = Receipts(self)
        self.customers = Customers(self)
        self.products = Products(self)
        self.organizations = Organizations(self)
        self.retentions = Retentions(self)
        self.webhooks = Webhooks(self)
        self.tools = Tools(self)
        self.catalogs = Catalogs(self)
        
        logger.info(f"Facturapi inicializado en modo: {self.mode}")
    
    def health_check(self) -> dict:
        """
        Verifica el estado de la API de Facturapi.
        
        Returns:
            {'success': True, 'data': {'status': 'ok'}}
        """
        return self._request('GET', 'check')
    
    def _headers(self) -> dict:
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }
    
    def _request(self, method: str, endpoint: str, data: dict = None,
                 params: dict = None) -> dict:
        """Realiza petición a la API."""
        url = f"{self.base_url}/{endpoint}".rstrip('/')
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self._headers(),
                json=data,
                params=params,
                timeout=60
            )
            
            result = response.json() if response.text else {}
            
            if response.status_code >= 400:
                error_msg = result.get('message', f'Error {response.status_code}')
                logger.error(f"Error Facturapi: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg,
                    'status_code': response.status_code,
                    'details': result
                }
            
            return {'success': True, 'data': result}
            
        except requests.Timeout:
            return {'success': False, 'error': 'Timeout - Servidor no responde'}
        except requests.RequestException as e:
            return {'success': False, 'error': str(e)}

# Alias para compatibilidad
FacturapiClient = Facturapi

if __name__ == "__main__":
    print("📄 Facturapi SDK Python - Test\n")
    
    api_key = os.getenv('FACTURAPI_KEY')
    
    if not api_key:
        print("⚠️ FACTURAPI_KEY no configurada")
        print("\nConfigura en .env:")
        print("  FACTURAPI_KEY=sk_test_xxxxxxxxx")
        print("\nEjemplo de uso:")
        print("""
from src.services.fiscal.facturapi_connector import Facturapi

facturapi = Facturapi("sk_test_xxx")

# Factura de contado
invoice = facturapi.invoices.create({
    "customer": {
        "legal_name": "Cliente SA",
        "tax_id": "ABC101010111",
        "tax_system": "601",
        "address": {"zip": "85900"}
    },
    "items": [{
        "quantity": 1,
        "product": {
            "description": "Producto",
            "product_key": "01010101",
            "price": 100.00,
            "taxes": [{"type": "IVA", "rate": 0.16}]
        }
    }],
    "payment_form": "01"  # Efectivo
})

print(invoice["data"]["uuid"])
        """)
    else:
        print(f"✅ API Key: {api_key[:15]}...")
        facturapi = Facturapi(api_key)
        print(f"✅ Modo: {facturapi.mode}")
