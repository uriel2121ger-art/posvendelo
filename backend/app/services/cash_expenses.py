"""
Cash Expenses - Registro de gastos en efectivo (Proveedores B)
Gastos de calle que no entran a contabilidad formal pero afectan utilidad real
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal
import logging
from pathlib import Path
import sys

logger = logging.getLogger(__name__)

class CashExpenses:
    """
    Registro de gastos en efectivo para proveedores informales.
    - Frutas y verduras locales
    - Servicios de calle (plomero, electricista)
    - Propinas y favores
    - Cualquier gasto que no tenga factura
    
    Estos gastos restan de la utilidad real del Wealth Dashboard.
    """
    
    CATEGORIES = [
        'mercancia',        # Productos para venta
        'insumos',          # Materiales de operación
        'servicios',        # Plomero, electricista, etc.
        'transporte',       # Fletes, gasolina
        'comida',           # Comidas del personal
        'propinas',         # Propinas, favores
        'mantenimiento',    # Reparaciones menores
        'otros'             # Misceláneos
    ]
    
    def __init__(self, core):
        self.core = core
        self._ensure_table()
    
    def _ensure_table(self):
        """Crea tabla si no existe."""
        self.core.db.execute_write("""
            CREATE TABLE IF NOT EXISTS cash_expenses (
                id BIGSERIAL PRIMARY KEY,
                branch_id INTEGER DEFAULT 1,
                category TEXT NOT NULL,
                description TEXT,
                amount REAL NOT NULL,
                vendor_name TEXT,
                vendor_phone TEXT,
                receipt_photo TEXT,
                payment_method TEXT DEFAULT 'cash',
                reference TEXT,
                registered_by INTEGER,
                expense_date TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                synced INTEGER DEFAULT 0
            )
        """)
        
        self.core.db.execute_write("""
            CREATE INDEX IF NOT EXISTS idx_cash_expenses_date ON cash_expenses(expense_date)
        """)
        self.core.db.execute_write("""
            CREATE INDEX IF NOT EXISTS idx_cash_expenses_category ON cash_expenses(category)
        """)
    
    def register_expense(self, category: str, amount: float, 
                        description: str = None,
                        vendor_name: str = None,
                        vendor_phone: str = None,
                        expense_date: str = None,
                        branch_id: int = 1,
                        user_id: int = None) -> Dict[str, Any]:
        """Registra un gasto en efectivo."""
        if category not in self.CATEGORIES:
            return {'success': False, 'error': f'Categoría inválida. Usar: {self.CATEGORIES}'}
        
        if amount <= 0:
            return {'success': False, 'error': 'Monto debe ser mayor a 0'}
        
        if expense_date is None:
            expense_date = datetime.now().strftime('%Y-%m-%d')
        
        # Use RETURNING id for PostgreSQL compatibility
        # execute_write() returns the ID automatically in DatabaseManager
        # CRITICAL FIX: cash_expenses table uses 'timestamp' not 'expense_date'
        expense_id = self.core.db.execute_write("""
            INSERT INTO cash_expenses 
            (branch_id, category, description, amount, vendor_name, vendor_phone,
             registered_by, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (branch_id, category, description, amount, vendor_name, 
              vendor_phone, user_id, expense_date))
        
        # If execute_write doesn't return ID (legacy SQLite), try to get it
        if expense_id == 0 or expense_id is None:
            # Fallback: try RETURNING or last_insert_rowid
            try:
                result = self.core.db.execute_query("""
                    SELECT id FROM cash_expenses
                    WHERE branch_id = %s AND category = %s AND amount = %s
                    ORDER BY created_at DESC LIMIT 1
                """, (branch_id, category, amount))
                # FIX 2026-02-01: Validar result con len() antes de acceder a [0]
                if result and len(result) > 0:
                    expense_id = result[0].get('id') if isinstance(result[0], dict) else result[0][0]
            except Exception:
                expense_id = 0
        
        logger.info(f"💸 Gasto registrado: ${amount:.2f} - {category}")
        
        return {
            'success': True,
            'expense_id': expense_id,
            'category': category,
            'amount': amount
        }
    
    def get_expenses_by_period(self, start_date: str, end_date: str, 
                               branch_id: int = None) -> List[Dict]:
        """Obtiene gastos en un período."""
        # CRITICAL FIX: cash_expenses table uses 'timestamp' not 'expense_date'
        sql = """
            SELECT * FROM cash_expenses
            WHERE CAST(timestamp AS DATE) BETWEEN %s AND %s
        """
        params = [start_date, end_date]
        
        if branch_id:
            sql += " AND branch_id = %s"
            params.append(branch_id)
        
        sql += " ORDER BY timestamp DESC"
        
        return list(self.core.db.execute_query(sql, tuple(params)))
    
    def get_summary_by_category(self, start_date: str = None, 
                                end_date: str = None) -> Dict[str, Any]:
        """Resumen de gastos por categoría."""
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        # CRITICAL FIX: cash_expenses table uses 'timestamp' not 'expense_date'
        sql = """
            SELECT category, COUNT(*) as count, COALESCE(SUM(amount), 0) as total
            FROM cash_expenses
            WHERE CAST(timestamp AS DATE) BETWEEN %s AND %s
            GROUP BY category
            ORDER BY total DESC
        """
        
        by_category = list(self.core.db.execute_query(sql, (start_date, end_date)))
        
        total = sum(float(c['total'] or 0) for c in by_category)
        
        return {
            'period': {'start': start_date, 'end': end_date},
            'by_category': [{
                'category': c['category'],
                'count': c['count'],
                'total': float(c['total'] or 0),
                'percentage': round(float(c['total'] or 0) / total * 100, 1) if total > 0 else 0
            } for c in by_category],
            'total': total
        }
    
    def get_monthly_trend(self, months: int = 6) -> List[Dict]:
        """Tendencia mensual de gastos."""
        results = []
        
        for i in range(months):
            month_start = (datetime.now().replace(day=1) - timedelta(days=30*i))
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            # CRITICAL FIX: cash_expenses table uses 'timestamp' not 'expense_date'
            sql = """
                SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as count
                FROM cash_expenses
                WHERE CAST(timestamp AS DATE) BETWEEN %s AND %s
            """
            result = list(self.core.db.execute_query(
                sql, (month_start.strftime('%Y-%m-%d'), month_end.strftime('%Y-%m-%d'))
            ))
            
            results.append({
                'month': month_start.strftime('%Y-%m'),
                'total': float(result[0]['total'] or 0) if result else 0,
                'count': result[0]['count'] if result else 0
            })
        
        return list(reversed(results))
    
    def get_vendor_summary(self) -> List[Dict]:
        """Resumen de gastos por proveedor."""
        sql = """
            SELECT vendor_name, vendor_phone, 
                   COUNT(*) as transactions,
                   COALESCE(SUM(amount), 0) as total,
                   MAX(expense_date) as last_expense
            FROM cash_expenses
            WHERE vendor_name IS NOT NULL
            GROUP BY vendor_name
            ORDER BY total DESC
            LIMIT 20
        """
        return list(self.core.db.execute_query(sql))
    
    def get_for_wealth_dashboard(self, year: int = None) -> Dict[str, Any]:
        """Obtiene datos para integrar con Wealth Dashboard."""
        if year is None:
            year = datetime.now().year
        
        # Total gastos del año
        sql = """
            SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as count
            FROM cash_expenses
            WHERE EXTRACT(YEAR FROM expense_date::timestamp) = %s
        """
        result = list(self.core.db.execute_query(sql, (str(year),)))

        # FIX 2026-01-30: Validar que result no esté vacío antes de acceder a [0]
        total_year = float(result[0]['total'] or 0) if result else 0

        # Este mes
        this_month = datetime.now().strftime('%Y-%m')
        sql_month = """
            SELECT COALESCE(SUM(amount), 0) as total
            FROM cash_expenses
            WHERE TO_CHAR(expense_date::timestamp, 'YYYY-MM') = %s
        """
        result_month = list(self.core.db.execute_query(sql_month, (this_month,)))
        # FIX 2026-01-30: Validar que result_month no esté vacío
        total_month = float(result_month[0]['total'] or 0) if result_month else 0

        return {
            'year': year,
            'total_year': total_year,
            'total_month': total_month,
            'count_year': result[0]['count'] if result else 0,
            'deduct_from_utility': True,
            'type': 'cash_expense_b'
        }
    
    def quick_register(self, amount: float, what: str) -> Dict[str, Any]:
        """Registro rápido desde PWA."""
        # Detectar categoría automáticamente
        what_lower = what.lower()
        
        if any(k in what_lower for k in ['fruta', 'verdura', 'carne', 'pollo', 'producto']):
            category = 'mercancia'
        elif any(k in what_lower for k in ['plomero', 'electrico', 'limpieza', 'servicio']):
            category = 'servicios'
        elif any(k in what_lower for k in ['flete', 'gas', 'uber', 'taxi']):
            category = 'transporte'
        elif any(k in what_lower for k in ['comida', 'almuerzo', 'cena', 'torta']):
            category = 'comida'
        elif any(k in what_lower for k in ['propina', 'viene', 'favor']):
            category = 'propinas'
        else:
            category = 'otros'
        
        return self.register_expense(
            category=category,
            amount=amount,
            description=what
        )
    
    def get_expenses_by_range(self, date_from: str = None, date_to: str = None) -> List[Dict]:
        """
        Obtiene gastos filtrados por rango de fechas.
        
        Args:
            date_from: Fecha inicio (YYYY-MM-DD), default: hace 30 días
            date_to: Fecha fin (YYYY-MM-DD), default: hoy
            
        Returns:
            Lista de gastos en el rango
        """
        if date_from is None:
            date_from = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        if date_to is None:
            date_to = datetime.now().strftime('%Y-%m-%d')
        
        # CRITICAL FIX: cash_expenses table uses 'timestamp' not 'expense_date'
        sql = """
            SELECT id, category, amount, description, timestamp as expense_date,
                   registered_by, receipt_photo, vendor_name, timestamp as created_at
            FROM cash_expenses
            WHERE CAST(timestamp AS DATE) BETWEEN %s AND %s
            ORDER BY timestamp DESC
        """
        
        expenses = [dict(e) for e in self.core.db.execute_query(sql, (date_from, date_to))]
        
        # Calcular totales
        total = sum(float(e.get('amount', 0)) for e in expenses)
        
        return {
            'date_from': date_from,
            'date_to': date_to,
            'expenses': expenses,
            'count': len(expenses),
            'total': total,
            'by_category': self._group_by_category(expenses)
        }
    
    def _group_by_category(self, expenses: List[Dict]) -> Dict[str, float]:
        """Agrupa gastos por categoría."""
        result = {}
        for e in expenses:
            cat = e.get('category', 'otros')
            result[cat] = result.get(cat, 0) + float(e.get('amount', 0))
        return result

# Función para integrar con Wealth Dashboard
def get_real_expenses_for_wealth(core) -> Dict:
    """
    Obtiene el total de gastos en efectivo para el cálculo 
    de utilidad real en Wealth Dashboard.
    """
    expenses = CashExpenses(core)
    return expenses.get_for_wealth_dashboard()
