"""
📄 Facturapi Connector - Integración Completa
Traducido de la documentación oficial PHP → Python (Asíncrono con httpx)
"""
from typing import Any, Dict, List
import logging
import os

logger = logging.getLogger("FACTURAPI")

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False
    logger.warning("httpx no instalado. Ejecutar: pip install httpx")

class FacturapiResource:
    def __init__(self, client: 'Facturapi', resource_name: str):
        self.client = client
        self.resource_name = resource_name
    
    async def _request(self, method: str, endpoint: str = '', data: dict = None, params: dict = None) -> dict:
        return await self.client._request(method, f"{self.resource_name}/{endpoint}".rstrip('/'), data, params)

class Invoices(FacturapiResource):
    def __init__(self, client: 'Facturapi'):
        super().__init__(client, 'invoices')
    
    async def create(self, data: Dict[str, Any], options: Dict[str, Any] = None) -> dict:
        params = {}
        if options and options.get('async'):
            params['async'] = 'true'
        return await self._request('POST', '', data, params)
    
    async def create_income(self, customer: dict, items: list, payment_form: str, payment_method: str = 'PUE', **kwargs) -> dict:
        data = {"type": "I", "customer": customer, "items": items, "payment_form": payment_form, "payment_method": payment_method, **kwargs}
        return await self.create(data)
    
    async def create_credit_note(self, customer: dict, items: list, related_uuid: str, payment_form: str = "28") -> dict:
        data = {"type": "E", "customer": customer, "items": items, "payment_form": payment_form, "related_documents": [{"relationship": "01", "documents": [related_uuid] if isinstance(related_uuid, str) else related_uuid}]}
        return await self.create(data)
    
    async def create_payment(self, customer: dict, payments: list) -> dict:
        data = {"type": "P", "customer": customer, "complements": [{"type": "pago", "data": payments}]}
        return await self.create(data)
    
    async def create_payroll(self, employee: dict, payroll_data: dict, folio_number: int = None, series: str = "N") -> dict:
        data = {"type": "N", "series": series, "customer": employee, "complements": [{"type": "nomina", "data": payroll_data}]}
        if folio_number: data["folio_number"] = folio_number
        return await self.create(data)
    
    async def create_substitute(self, customer: dict, items: list, canceled_uuid: str, payment_form: str) -> dict:
        data = {"type": "I", "customer": customer, "items": items, "payment_form": payment_form, "related_documents": [{"relationship": "04", "documents": [canceled_uuid]}]}
        return await self.create(data)
    
    async def create_draft(self, data: Dict[str, Any]) -> dict:
        data["status"] = "draft"
        return await self.create(data)
    
    async def update_draft(self, invoice_id: str, data: Dict[str, Any]) -> dict:
        return await self._request('PUT', invoice_id, data)
    
    async def stamp_draft(self, invoice_id: str) -> dict:
        return await self._request('POST', f"{invoice_id}/stamp")
    
    async def get(self, invoice_id: str) -> dict:
        return await self._request('GET', invoice_id)
    
    async def list(self, params: dict = None) -> dict:
        return await self._request('GET', '', params=params)
    
    async def cancel(self, invoice_id: str, motive: str = "02", substitution: str = None) -> dict:
        params = {"motive": motive}
        if motive == "01" and substitution: params["substitution"] = substitution
        return await self._request('DELETE', invoice_id, params=params)
    
    async def download_pdf(self, invoice_id: str) -> bytes:
        url = f"{self.client.base_url}/invoices/{invoice_id}/pdf"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.client._headers(), timeout=60)
            if response.status_code >= 400: raise Exception(f"Error {response.status_code}: {response.text}")
            return response.content
    
    async def download_xml(self, invoice_id: str) -> str:
        url = f"{self.client.base_url}/invoices/{invoice_id}/xml"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.client._headers(), timeout=60)
            if response.status_code >= 400: raise Exception(f"Error {response.status_code}: {response.text}")
            return response.text
    
    async def send_by_email(self, invoice_id: str, email: str = None) -> dict:
        data = {}
        if email: data["email"] = email
        return await self._request('POST', f"{invoice_id}/email", data)
    
    async def copy_to_draft(self, invoice_id: str) -> dict:
        return await self._request('POST', f"{invoice_id}/copy")
    
    async def preview_pdf(self, data: Dict[str, Any]) -> bytes:
        url = f"{self.client.base_url}/invoices/preview"
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=self.client._headers(), json=data, timeout=60)
            return response.content
    
    async def download_zip(self, invoice_id: str) -> bytes:
        url = f"{self.client.base_url}/invoices/{invoice_id}/zip"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.client._headers(), timeout=60)
            if response.status_code >= 400: raise Exception(f"Error {response.status_code}: {response.text}")
            return response.content
    
    async def download_cancellation_receipt(self, invoice_id: str, format: str = "xml") -> bytes:
        url = f"{self.client.base_url}/invoices/{invoice_id}/cancellation_receipt/{format}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.client._headers(), timeout=60)
            return response.content
    
    async def update_status(self, invoice_id: str) -> dict:
        return await self._request('PUT', f"{invoice_id}/status")

class Receipts(FacturapiResource):
    def __init__(self, client: 'Facturapi'):
        super().__init__(client, 'receipts')
    
    async def create(self, data: Dict[str, Any]) -> dict:
        return await self._request('POST', '', data)
    
    async def get(self, receipt_id: str) -> dict:
        return await self._request('GET', receipt_id)
    
    async def list(self, params: dict = None) -> dict:
        return await self._request('GET', '', params=params)
    
    async def invoice(self, receipt_id: str, invoice_data: Dict[str, Any]) -> dict:
        return await self._request('POST', f"{receipt_id}/invoice", invoice_data)
    
    async def assign_customer(self, receipt_id: str, customer_id: str) -> dict:
        return await self._request('PUT', receipt_id, {"customer": customer_id})
    
    async def cancel(self, receipt_id: str) -> dict:
        return await self._request('DELETE', receipt_id)
    
    async def create_global_invoice(self, receipt_ids: list, periodicity: str = "month", month: str = None, year: str = None) -> dict:
        data = {"periodicity": periodicity, "receipts": receipt_ids}
        if month: data["month"] = month
        if year: data["year"] = year
        return await self.client._request('POST', 'invoices', data)

class Customers(FacturapiResource):
    def __init__(self, client: 'Facturapi'):
        super().__init__(client, 'customers')
    
    async def create(self, data: Dict[str, Any], options: Dict[str, Any] = None) -> dict:
        params = {}
        if options and options.get('createEditLink'): params['createEditLink'] = 'true'
        return await self._request('POST', '', data, params)
    
    async def retrieve(self, customer_id: str) -> dict:
        return await self._request('GET', customer_id)
    
    async def get(self, customer_id: str) -> dict:
        return await self._request('GET', customer_id)
    
    async def list(self, params: dict = None) -> dict:
        return await self._request('GET', '', params=params)
    
    async def search_by_rfc(self, rfc: str) -> dict:
        result = await self.list({"tax_id": rfc})
        if result.get('success') and result.get('data', {}).get('data'):
            return {'success': True, 'data': result['data']['data'][0]}
        return {'success': False, 'error': 'Cliente no encontrado'}
    
    async def update(self, customer_id: str, data: Dict[str, Any] = None, options: Dict[str, Any] = None) -> dict:
        params = {}
        if options and options.get('createEditLink'): params['createEditLink'] = 'true'
        return await self._request('PUT', customer_id, data or {}, params)
    
    async def send_edit_link_by_email(self, customer_id: str, email: str = None) -> dict:
        data = {}
        if email: data["email"] = email
        return await self._request('POST', f"{customer_id}/edit-link/email", data)
    
    async def delete(self, customer_id: str) -> dict:
        return await self._request('DELETE', customer_id)

class Products(FacturapiResource):
    def __init__(self, client: 'Facturapi'):
        super().__init__(client, 'products')
    
    async def create(self, data: Dict[str, Any]) -> dict:
        return await self._request('POST', '', data)
    
    async def create_with_tax_included(self, description: str, product_key: str, price: float, sku: str = None, unit_key: str = "H87", iva_rate: float = 0.16) -> dict:
        data = {"description": description, "product_key": product_key, "unit_key": unit_key, "price": price, "tax_included": True, "taxes": [{"type": "IVA", "rate": iva_rate}]}
        if sku: data["sku"] = sku
        return await self.create(data)
    
    async def create_without_tax(self, description: str, product_key: str, price: float, sku: str = None, unit_key: str = "H87", iva_rate: float = 0.16) -> dict:
        data = {"description": description, "product_key": product_key, "unit_key": unit_key, "price": price, "tax_included": False, "taxes": [{"type": "IVA", "rate": iva_rate}]}
        if sku: data["sku"] = sku
        return await self.create(data)
    
    async def create_exempt(self, description: str, product_key: str, price: float, sku: str = None, unit_key: str = "H87") -> dict:
        data = {"description": description, "product_key": product_key, "unit_key": unit_key, "price": price, "tax_included": False, "taxes": [{"type": "IVA", "factor": "Exento", "rate": 0}]}
        if sku: data["sku"] = sku
        return await self.create(data)
    
    async def get(self, product_id: str) -> dict:
        return await self._request('GET', product_id)
    
    async def list(self, params: dict = None) -> dict:
        return await self._request('GET', '', params=params)
    
    async def search(self, query: str) -> dict:
        return await self.list({"q": query})
    
    async def update(self, product_id: str, data: Dict[str, Any]) -> dict:
        return await self._request('PUT', product_id, data)
    
    async def delete(self, product_id: str) -> dict:
        return await self._request('DELETE', product_id)

class Organizations(FacturapiResource):
    def __init__(self, client: 'Facturapi'):
        super().__init__(client, 'organizations')
    
    async def create(self, data: Dict[str, Any]) -> dict:
        return await self._request('POST', '', data)
    
    async def get(self, org_id: str = None) -> dict:
        if org_id: return await self._request('GET', org_id)
        return await self._request('GET', '')
    
    async def update_legal(self, org_id: str, data: Dict[str, Any]) -> dict:
        return await self._request('PUT', f"{org_id}/legal", data)
    
    async def upload_certificates(self, org_id: str, cer_base64: str, key_base64: str, password: str) -> dict:
        data = {"cer": cer_base64, "key": key_base64, "password": password}
        return await self._request('PUT', f"{org_id}/certificates", data)

class Tools(FacturapiResource):
    def __init__(self, client: 'Facturapi'):
        super().__init__(client, 'tools')
    
    async def validate_rfc(self, rfc: str) -> dict:
        return await self._request('GET', 'tax_id_validation', params={"tax_id": rfc})

class Catalogs(FacturapiResource):
    def __init__(self, client: 'Facturapi'):
        super().__init__(client, 'catalogs')
    
    async def get(self, catalog_type: str, params: dict = None) -> dict:
        return await self._request('GET', catalog_type, params=params)
    
    async def product_keys(self, query: str = None) -> dict:
        params = {"q": query} if query else None
        return await self.get('product_keys', params)
    
    async def unit_keys(self) -> dict:
        return await self.get('unit_keys')

class Retentions(FacturapiResource):
    def __init__(self, client: 'Facturapi'):
        super().__init__(client, 'retentions')
    
    async def create(self, data: Dict[str, Any]) -> dict:
        return await self._request('POST', '', data)
    
    async def get(self, retention_id: str) -> dict:
        return await self._request('GET', retention_id)
    
    async def list(self, params: dict = None) -> dict:
        return await self._request('GET', '', params=params)
    
    async def cancel(self, retention_id: str) -> dict:
        return await self._request('DELETE', retention_id)
    
    async def download_pdf(self, retention_id: str) -> bytes:
        url = f"{self.client.base_url}/retentions/{retention_id}/pdf"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.client._headers(), timeout=60)
            return response.content
    
    async def download_xml(self, retention_id: str) -> str:
        url = f"{self.client.base_url}/retentions/{retention_id}/xml"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.client._headers(), timeout=60)
            return response.text
    
    async def send_by_email(self, retention_id: str, email: str = None) -> dict:
        data = {"email": email} if email else {}
        return await self._request('POST', f"{retention_id}/email", data)

class Webhooks(FacturapiResource):
    def __init__(self, client: 'Facturapi'):
        super().__init__(client, 'webhooks')
    
    async def create(self, url: str, events: List[str] = None) -> dict:
        data = {"url": url}
        if events: data["enabled_events"] = events
        return await self._request('POST', '', data)
    
    async def get(self, webhook_id: str) -> dict:
        return await self._request('GET', webhook_id)
    
    async def list(self) -> dict:
        return await self._request('GET', '')
    
    async def update(self, webhook_id: str, data: Dict[str, Any]) -> dict:
        return await self._request('PUT', webhook_id, data)
    
    async def delete(self, webhook_id: str) -> dict:
        return await self._request('DELETE', webhook_id)
    
    def validate_signature(self, payload: str, signature: str, webhook_secret: str) -> bool:
        import hashlib
        import hmac
        expected = hmac.new(webhook_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

class Facturapi:
    BASE_URL = "https://www.facturapi.io/v2"
    
    def __init__(self, api_key: str = None):
        if not HAS_HTTPX:
            raise ImportError("Se requiere 'httpx'. Ejecutar: pip install httpx")
        
        self.api_key = api_key or os.getenv('FACTURAPI_KEY')
        if not self.api_key:
            raise ValueError("API Key requerida. Configurar FACTURAPI_KEY o pasar como parámetro.")
        
        self.base_url = self.BASE_URL
        self.mode = 'test' if 'test' in self.api_key else 'live'
        
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
    
    async def health_check(self) -> dict:
        return await self._request('GET', 'check')
    
    def _headers(self) -> dict:
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }
    
    async def _request(self, method: str, endpoint: str, data: dict = None, params: dict = None) -> dict:
        url = f"{self.base_url}/{endpoint}".rstrip('/')
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=self._headers(),
                    json=data,
                    params=params,
                    timeout=60.0
                )
                
                result = response.json() if response.text else {}
                
                if response.status_code >= 400:
                    error_msg = result.get('message', f'Error {response.status_code}')
                    logger.error(f"Error Facturapi: {error_msg}")
                    return {'success': False, 'error': error_msg, 'status_code': response.status_code, 'details': result}
                
                return {'success': True, 'data': result}
                
        except httpx.TimeoutException:
            return {'success': False, 'error': 'Timeout - Servidor no responde'}
        except httpx.RequestError as e:
            return {'success': False, 'error': str(e)}

FacturapiClient = Facturapi
