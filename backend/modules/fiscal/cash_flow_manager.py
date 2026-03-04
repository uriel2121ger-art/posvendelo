"""
Cash Extraction - Gestión de liquidez y contratos donación/mutuo
Art. 93 Fracc. XXIII LISR
"""

from typing import Any, Dict, List
from datetime import datetime
from decimal import Decimal
import hashlib
import logging

from modules.shared.constants import money

logger = logging.getLogger(__name__)


class CashExtractionEngine:
    LIMITE_INFORMABLE = Decimal('600000.00')
    UMBRAL_FECHA_CIERTA = Decimal('100000.00')
    PARENTESCOS = {'padre': 'Padre', 'madre': 'Madre', 'hijo': 'Hijo/Hija', 'abuelo': 'Abuelo/Abuela', 'nieto': 'Nieto/Nieta', 'conyuge': 'Cónyuge'}

    def __init__(self, db):
        self.db = db

    async def setup_tables(self):
        try:
            await self.db.execute("""
                CREATE TABLE IF NOT EXISTS related_persons (
                    id BIGSERIAL PRIMARY KEY, name TEXT NOT NULL, rfc TEXT, curp TEXT,
                    parentesco TEXT NOT NULL, address TEXT, phone TEXT, is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await self.db.execute("""
                CREATE TABLE IF NOT EXISTS cash_extractions (
                    id BIGSERIAL PRIMARY KEY, amount DECIMAL(15,2) NOT NULL, extraction_date TEXT NOT NULL,
                    document_type TEXT NOT NULL, related_person_id INTEGER, beneficiary_name TEXT,
                    purpose TEXT, contract_hash TEXT, contract_path TEXT, requires_notary INTEGER DEFAULT 0,
                    notary_date TEXT, notary_number TEXT, banked INTEGER DEFAULT 0, bank_date TEXT,
                    status TEXT DEFAULT 'pending', created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (related_person_id) REFERENCES related_persons(id)
                )
            """)
            await self.db.execute("CREATE INDEX IF NOT EXISTS idx_extractions_date ON cash_extractions(extraction_date)")
        except Exception as e:
            logger.error(f"Error creating tables: {e}")

    async def add_related_person(self, name: str, parentesco: str, rfc: str = None, curp: str = None) -> Dict[str, Any]:
        if parentesco not in self.PARENTESCOS:
            return {'success': False, 'error': f'Parentesco inválido'}
        try:
            await self.db.execute("INSERT INTO related_persons (name, rfc, curp, parentesco, created_at) VALUES (:name, :rfc, :curp, :par, :ts)",
                name=name, rfc=rfc, curp=curp, par=parentesco, ts=datetime.now().isoformat())
            return {'success': True, 'message': f'{name} agregado como {self.PARENTESCOS[parentesco]}'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def get_serie_b_balance(self) -> Dict[str, Any]:
        year = datetime.now().year
        year_start = f"{year}-01-01"
        year_end = f"{year + 1}-01-01"
        r = await self.db.fetchrow("SELECT COALESCE(SUM(total), 0) as total_serie_b, COUNT(*) as transacciones FROM sales WHERE serie = 'B' AND timestamp >= :ys AND timestamp < :ye AND status = 'completed'", ys=year_start, ye=year_end)
        total_b = Decimal(str(r['total_serie_b'] or 0)) if r else Decimal('0')

        ext = await self.db.fetchrow("SELECT COALESCE(SUM(amount), 0) as total FROM cash_extractions WHERE extraction_date >= :ys AND extraction_date < :ye", ys=year_start, ye=year_end)
        total_extracted = Decimal(str(ext['total'] or 0)) if ext else Decimal('0')

        return {'year': year, 'total_serie_b': money(total_b), 'total_extracted': money(total_extracted), 'available': money(total_b - total_extracted), 'transactions': r['transacciones'] if r else 0}

    async def create_extraction(self, amount: float, document_type: str, related_person_id: int = None, purpose: str = None) -> Dict[str, Any]:
        amount = Decimal(str(amount))
        balance = await self.get_serie_b_balance()
        if amount > Decimal(str(balance['available'])):
            return {'success': False, 'error': f'Monto excede disponible (${balance["available"]:,.2f})'}

        person = None
        if related_person_id:
            person = await self.db.fetchrow("SELECT * FROM related_persons WHERE id = :rid", rid=related_person_id)

        requires_notary = amount >= self.UMBRAL_FECHA_CIERTA
        contract_data = f"{amount}|{document_type}|{datetime.now().isoformat()}|{person['name'] if person else 'N/A'}"
        contract_hash = hashlib.sha256(contract_data.encode()).hexdigest()

        try:
            await self.db.execute("""
                INSERT INTO cash_extractions (amount, extraction_date, document_type, related_person_id,
                    beneficiary_name, purpose, contract_hash, requires_notary, status, created_at)
                VALUES (:amt, :dt, :dtype, :rpid, :bname, :purpose, :hash, :rn, 'pending', :ts)
            """, amt=amount.quantize(Decimal('0.01')), dt=datetime.now().strftime('%Y-%m-%d'), dtype=document_type,
                rpid=related_person_id, bname=person['name'] if person else None, purpose=purpose,
                hash=contract_hash, rn=1 if requires_notary else 0, ts=datetime.now().isoformat())

            result = {'success': True, 'amount': money(amount), 'type': document_type, 'hash': contract_hash[:16] + '...', 'requires_notary': requires_notary}
            if requires_notary:
                result['warning'] = f'Monto superior a ${money(self.UMBRAL_FECHA_CIERTA):,.0f}. Recomendable fecha cierta ante Notario.'
            return result
        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def generate_contract_text(self, extraction_id: int) -> str:
        e = await self.db.fetchrow("""
            SELECT e.*, p.name as donor_name, p.rfc as donor_rfc, p.parentesco
            FROM cash_extractions e LEFT JOIN related_persons p ON e.related_person_id = p.id WHERE e.id = :eid
        """, eid=extraction_id)
        if not e: return "Extracción no encontrada"
        fecha = datetime.now()
        return f"""CONTRATO DE {e['document_type']}
Fecha: {fecha.strftime('%d de %B de %Y')}
Monto: ${money(e['amount']):,.2f} MXN
Donante/Mutuante: {e.get('donor_name', 'N/A')} (RFC: {e.get('donor_rfc', 'N/A')})
Parentesco: {self.PARENTESCOS.get(e.get('parentesco', ''), 'N/A')}
Hash: {e['contract_hash']}
{'REQUIERE RATIFICACIÓN NOTARIAL' if e.get('requires_notary') else ''}"""

    async def get_annual_summary(self, year: int = None) -> Dict[str, Any]:
        year = year or datetime.now().year
        year_start = f"{year}-01-01"
        year_end = f"{year + 1}-01-01"
        result = await self.db.fetch("""
            SELECT document_type, COUNT(*) as count, COALESCE(SUM(amount), 0) as total,
                COALESCE(SUM(CASE WHEN requires_notary = 1 THEN 1 ELSE 0 END), 0) as notarized
            FROM cash_extractions WHERE extraction_date >= :ys AND extraction_date < :ye GROUP BY document_type
        """, ys=year_start, ye=year_end)
        total = sum((Decimal(str(r['total'] or 0)) for r in result), Decimal('0'))
        return {'year': year, 'by_type': {r['document_type']: dict(r) for r in result}, 'total_extracted': money(total),
                'limite_informable': money(self.LIMITE_INFORMABLE), 'requires_annual_declaration': total >= self.LIMITE_INFORMABLE}
