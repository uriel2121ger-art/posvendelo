"""
Cash Extraction Module - Gestión de liquidez y contratos de donación/mutuo
Art. 93 Fracc. XXIII LISR - Donativos exentos en línea recta
"""

from typing import Any, Dict, List, Optional
from datetime import date, datetime
from decimal import Decimal
import hashlib
import logging

logger = logging.getLogger(__name__)

class CashExtractionEngine:
    """
    Motor de gestión de extracciones de efectivo.
    Genera contratos de donación/mutuo para bancarización legal.
    """
    
    # Límite anual para informar donativos (Art. 93 LISR)
    LIMITE_INFORMABLE = Decimal('600000.00')
    # Umbral para recomendar fecha cierta (notarial)
    UMBRAL_FECHA_CIERTA = Decimal('100000.00')
    
    PARENTESCOS = {
        'padre': 'Padre',
        'madre': 'Madre', 
        'hijo': 'Hijo/Hija',
        'abuelo': 'Abuelo/Abuela',
        'nieto': 'Nieto/Nieta',
        'conyuge': 'Cónyuge'
    }
    
    def __init__(self, core):
        self.core = core
        self._setup_tables()
    
    def _setup_tables(self):
        """Crea tablas necesarias."""
        try:
            # Tabla de familiares/relacionados
            self.core.db.execute_write("""
                CREATE TABLE IF NOT EXISTS related_persons (
                    id BIGSERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    rfc TEXT,
                    curp TEXT,
                    parentesco TEXT NOT NULL,
                    address TEXT,
                    phone TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Tabla de extracciones
            self.core.db.execute_write("""
                CREATE TABLE IF NOT EXISTS cash_extractions (
                    id BIGSERIAL PRIMARY KEY,
                    amount DECIMAL(15,2) NOT NULL,
                    extraction_date TEXT NOT NULL,
                    document_type TEXT NOT NULL,
                    related_person_id INTEGER,
                    beneficiary_name TEXT,
                    purpose TEXT,
                    contract_hash TEXT,
                    contract_path TEXT,
                    requires_notary INTEGER DEFAULT 0,
                    notary_date TEXT,
                    notary_number TEXT,
                    banked INTEGER DEFAULT 0,
                    bank_date TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (related_person_id) REFERENCES related_persons(id)
                )
            """)
            
            self.core.db.execute_write(
                "CREATE INDEX IF NOT EXISTS idx_extractions_date ON cash_extractions(extraction_date)"
            )
            
        except Exception as e:
            logger.error(f"Error creating tables: {e}")
    
    def add_related_person(self, name: str, parentesco: str,
                           rfc: str = None, curp: str = None) -> Dict[str, Any]:
        """Agrega un familiar para contratos."""
        if parentesco not in self.PARENTESCOS:
            return {'success': False, 'error': f'Parentesco inválido. Use: {list(self.PARENTESCOS.keys())}'}
        
        try:
            self.core.db.execute_write(
                """INSERT INTO related_persons (name, rfc, curp, parentesco, created_at)
                   VALUES (%s, %s, %s, %s, %s)""",
                (name, rfc, curp, parentesco, datetime.now().isoformat())
            )
            
            return {
                'success': True,
                'message': f'{name} agregado como {self.PARENTESCOS[parentesco]}'
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_serie_b_balance(self) -> Dict[str, Any]:
        """Obtiene balance acumulado de Serie B."""
        year = datetime.now().year
        
        sql = """
            SELECT 
                COALESCE(SUM(total), 0) as total_serie_b,
                COUNT(*) as transacciones
            FROM sales
            WHERE serie = 'B'
            AND EXTRACT(YEAR FROM timestamp::timestamp) = %s
            AND status = 'completed'
        """
        result = list(self.core.db.execute_query(sql, (str(year),)))
        
        total_b = Decimal(str(result[0]['total_serie_b'] or 0)) if result else Decimal('0')
        
        # Obtener extracciones ya hechas
        extracted = list(self.core.db.execute_query(
            """SELECT COALESCE(SUM(amount), 0) as total FROM cash_extractions
               WHERE EXTRACT(YEAR FROM extraction_date::timestamp) = %s""",
            (str(year),)
        ))
        total_extracted = Decimal(str(extracted[0]['total'] or 0)) if extracted else Decimal('0')
        
        available = total_b - total_extracted
        
        return {
            'year': year,
            'total_serie_b': float(total_b),
            'total_extracted': float(total_extracted),
            'available': float(available),
            'transactions': result[0]['transacciones'] if result else 0
        }
    
    def create_extraction(self, amount: float, document_type: str,
                          related_person_id: int = None,
                          purpose: str = None) -> Dict[str, Any]:
        """
        Crea una extracción de efectivo con contrato.
        
        Args:
            amount: Monto a extraer
            document_type: 'DONACION' o 'MUTUO'
            related_person_id: ID del familiar donante/prestador
            purpose: Descripción del uso
        """
        amount = Decimal(str(amount))
        
        # Verificar disponibilidad
        balance = self.get_serie_b_balance()
        if amount > Decimal(str(balance['available'])):
            return {
                'success': False,
                'error': f'Monto excede disponible (${balance["available"]:,.2f})'
            }
        
        # Obtener persona relacionada
        person = None
        if related_person_id:
            p = list(self.core.db.execute_query(
                "SELECT * FROM related_persons WHERE id = %s",
                (related_person_id,)
            ))
            if p:
                person = p[0]
        
        # Determinar si requiere fecha cierta
        requires_notary = amount >= self.UMBRAL_FECHA_CIERTA
        
        # Generar hash del contrato
        contract_data = f"{amount}|{document_type}|{datetime.now().isoformat()}|{person['name'] if person else 'N/A'}"
        contract_hash = hashlib.sha256(contract_data.encode()).hexdigest()
        
        try:
            self.core.db.execute_write(
                """INSERT INTO cash_extractions
                   (amount, extraction_date, document_type, related_person_id,
                    beneficiary_name, purpose, contract_hash, requires_notary,
                    status, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s)""",
                (float(amount), datetime.now().strftime('%Y-%m-%d'),
                 document_type, related_person_id,
                 person['name'] if person else None, purpose,
                 contract_hash, 1 if requires_notary else 0,
                 datetime.now().isoformat())
            )
            
            result = {
                'success': True,
                'amount': float(amount),
                'type': document_type,
                'hash': contract_hash[:16] + '...',
                'requires_notary': requires_notary
            }
            
            if requires_notary:
                result['warning'] = (
                    f'⚠️ Monto superior a ${float(self.UMBRAL_FECHA_CIERTA):,.0f}. '
                    'Se recomienda fecha cierta ante Notario.'
                )
            
            # SECURITY: No loguear extracciones de efectivo
            pass
            
            return result
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def generate_contract_text(self, extraction_id: int) -> str:
        """Genera el texto del contrato de donación/mutuo."""
        ext = list(self.core.db.execute_query(
            """SELECT e.*, p.name as donor_name, p.rfc as donor_rfc, p.parentesco
               FROM cash_extractions e
               LEFT JOIN related_persons p ON e.related_person_id = p.id
               WHERE e.id = %s""",
            (extraction_id,)
        ))
        
        if not ext:
            return "Extracción no encontrada"
        
        e = ext[0]
        config = self.core.get_app_config()
        fiscal = self.core.get_fiscal_config()
        
        fecha = datetime.now()
        
        if e['document_type'] == 'DONACION':
            contract = self._generate_donation_contract(e, config, fiscal, fecha)
        else:
            contract = self._generate_loan_contract(e, config, fiscal, fecha)
        
        return contract
    
    def _generate_donation_contract(self, e: Dict, config: Dict, 
                                    fiscal: Dict, fecha: datetime) -> str:
        """Genera contrato de donación."""
        return f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    CONTRATO DE DONACIÓN ENTRE PARTICULARES                   ║
║                Art. 93, Fracción XXIII de la Ley del ISR                     ║
╚══════════════════════════════════════════════════════════════════════════════╝

En la ciudad de Mérida, Yucatán, a {fecha.strftime('%d de %B de %Y')}.

═══════════════════════════════════════════════════════════════════════════════
                              COMPARECIENTES
═══════════════════════════════════════════════════════════════════════════════

DONANTE:
Nombre:              {e.get('donor_name', 'N/A')}
RFC:                 {e.get('donor_rfc', 'N/A')}
Parentesco:          {self.PARENTESCOS.get(e.get('parentesco', ''), 'N/A')}

DONATARIO:
Nombre:              {config.get('owner_name', fiscal.get('emisor_nombre', 'N/A'))}
RFC:                 {fiscal.get('rfc_emisor', 'N/A')}

═══════════════════════════════════════════════════════════════════════════════
                              DECLARACIONES
═══════════════════════════════════════════════════════════════════════════════

I.   Las partes manifiestan ser mayores de edad, en pleno uso de sus facultades
     mentales y con capacidad legal para contratar y obligarse.

II.  Que es voluntad del DONANTE transmitir gratuitamente al DONATARIO la 
     cantidad que más adelante se señala.

III. Que el DONANTE y el DONATARIO son ascendientes y descendientes en línea 
     recta, por lo que esta donación se encuentra EXENTA conforme al Art. 93,
     Fracción XXIII de la Ley del Impuesto sobre la Renta.

═══════════════════════════════════════════════════════════════════════════════
                               CLÁUSULAS
═══════════════════════════════════════════════════════════════════════════════

PRIMERA.- OBJETO
El DONANTE transmite de forma gratuita al DONATARIO la cantidad de:

        ${float(e['amount']):,.2f} MXN
        ({self._num_to_words(e['amount'])} PESOS 00/100 M.N.)

SEGUNDA.- FUNDAMENTO LEGAL
Esta donación está exenta del Impuesto sobre la Renta conforme al Artículo 93,
Fracción XXIII de la Ley del ISR, al tratarse de una donación entre 
ascendientes y descendientes en línea recta.

TERCERA.- OBLIGACIÓN DE INFORMAR
Las partes reconocen que, de conformidad con el Artículo 90, penúltimo párrafo
de la LISR, si el monto de los donativos recibidos en el ejercicio excede de 
$600,000.00 MXN, el DONATARIO deberá informarlo en su declaración anual.

CUARTA.- ACEPTACIÓN
El DONATARIO acepta la donación en los términos aquí expresados.

═══════════════════════════════════════════════════════════════════════════════
                               FIRMAS
═══════════════════════════════════════════════════════════════════════════════

_____________________________          _____________________________
        DONANTE                               DONATARIO

Fecha: {fecha.strftime('%Y-%m-%d %H:%M:%S')}
Hash de Integridad: {e['contract_hash']}

{'⚠️ NOTA: Por el monto, se recomienda ratificar ante Notario Público.' if e.get('requires_notary') else ''}
"""
    
    def _generate_loan_contract(self, e: Dict, config: Dict,
                                fiscal: Dict, fecha: datetime) -> str:
        """Genera contrato de mutuo (préstamo)."""
        return f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    CONTRATO DE MUTUO (PRÉSTAMO) SIMPLE                       ║
║                      Art. 2384 del Código Civil                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

En la ciudad de Mérida, Yucatán, a {fecha.strftime('%d de %B de %Y')}.

═══════════════════════════════════════════════════════════════════════════════
                              COMPARECIENTES
═══════════════════════════════════════════════════════════════════════════════

MUTUANTE (Quien presta):
Nombre:              {e.get('donor_name', 'N/A')}
RFC:                 {e.get('donor_rfc', 'N/A')}

MUTUATARIO (Quien recibe):
Nombre:              {config.get('owner_name', fiscal.get('emisor_nombre', 'N/A'))}
RFC:                 {fiscal.get('rfc_emisor', 'N/A')}

═══════════════════════════════════════════════════════════════════════════════
                               CLÁUSULAS
═══════════════════════════════════════════════════════════════════════════════

PRIMERA.- OBJETO DEL CONTRATO
El MUTUANTE entrega en préstamo simple al MUTUATARIO la cantidad de:

        ${float(e['amount']):,.2f} MXN
        ({self._num_to_words(e['amount'])} PESOS 00/100 M.N.)

SEGUNDA.- PLAZO
El MUTUATARIO se obliga a devolver la cantidad prestada en un plazo de 
DOCE (12) meses contados a partir de la fecha de este contrato.

TERCERA.- INTERESES
Por tratarse de un préstamo entre familiares, las partes acuerdan que este
préstamo será SIN INTERESES (gratuito).

CUARTA.- FORMA DE PAGO
El pago podrá realizarse en una sola exhibición o en parcialidades, según
convenga al MUTUATARIO.

═══════════════════════════════════════════════════════════════════════════════
                               FIRMAS
═══════════════════════════════════════════════════════════════════════════════

_____________________________          _____________________________
     MUTUANTE                              MUTUATARIO

Fecha: {fecha.strftime('%Y-%m-%d %H:%M:%S')}
Hash: {e['contract_hash']}
"""
    
    def _num_to_words(self, num) -> str:
        """Convierte número a palabras (simplificado)."""
        n = int(float(num))
        if n >= 1000000:
            return f"{n // 1000000} MILLÓN(ES) {(n % 1000000) // 1000} MIL"
        elif n >= 1000:
            return f"{n // 1000} MIL {n % 1000}"
        return str(n)
    
    def get_annual_summary(self, year: int = None) -> Dict[str, Any]:
        """Resumen anual de extracciones."""
        year = year or datetime.now().year
        
        sql = """
            SELECT 
                document_type,
                COUNT(*) as count,
                COALESCE(SUM(amount), 0) as total,
                COALESCE(SUM(CASE WHEN requires_notary = 1 THEN 1 ELSE 0 END), 0) as notarized
            FROM cash_extractions
            WHERE EXTRACT(YEAR FROM extraction_date::timestamp) = %s
            GROUP BY document_type
        """
        result = list(self.core.db.execute_query(sql, (str(year),)))
        
        total = sum(float(r['total'] or 0) for r in result)
        requires_declaration = total >= float(self.LIMITE_INFORMABLE)
        
        return {
            'year': year,
            'by_type': {r['document_type']: dict(r) for r in result},
            'total_extracted': total,
            'limite_informable': float(self.LIMITE_INFORMABLE),
            'requires_annual_declaration': requires_declaration,
            'warning': '⚠️ Debe informar en declaración anual' if requires_declaration else None
        }
