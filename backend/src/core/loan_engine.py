"""
LOAN ENGINE - Employee Loans & Advances System
Manages employee loans, advances, and automatic commission deductions
"""

from typing import Any, Dict, List, Optional, TYPE_CHECKING
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
import secrets
import string
import logging

if TYPE_CHECKING:
    from src.infra.database import DatabaseManager

logger = logging.getLogger(__name__)


class LoanEngine:
    """Engine for managing employee loans and advances."""
    
    def __init__(self, db_manager: "DatabaseManager"):
        """Initialize the loan engine.
        
        Args:
            db_manager: DatabaseManager instance (supports SQLite and PostgreSQL)
        """
        self.db = db_manager
    
    # ========== EMPLOYEE MANAGEMENT ==========
    
    def generate_employee_code(self) -> str:
        """Generate  unique employee code (E001, E002, etc.)."""
        # PostgreSQL: SUBSTR → SUBSTRING, pero ambos funcionan
        result = self.db.execute_query(
            "SELECT MAX(CAST(SUBSTR(employee_code, 2) AS INTEGER)) FROM employees"
        )
        max_num = result[0][0] if result and len(result) > 0 and result[0] and result[0][0] else 0
        
        new_code = f"E{(max_num + 1):03d}"
        return new_code
    
    def create_employee(
        self,
        name: str,
        position: str = "",
        hire_date: str = None,
        phone: str = "",
        email: str = "",
        base_salary: float = 0.0,
        commission_rate: float = 0.0,
        loan_limit: float = 0.0,
        user_id: int = None,
        notes: str = ""
    ) -> int:
        """Create a new employee.
        
        Args:
            name: Employee full name
            position: Job position
            hire_date: ISO format date (YYYY-MM-DD)
            phone: Phone number
            email: Email address
            base_salary: Base monthly salary
            commission_rate: Commission percentage (0-100)
            loan_limit: Maximum loan amount allowed
            user_id: Link to users table (optional)
            notes: Additional notes
            
        Returns:
            Employee ID
        """
        import math

        # ===== VALIDACIONES WTF =====
        # Nombre requerido
        if not name or not isinstance(name, str):
            raise ValueError("name es requerido y debe ser string")
        name = name.strip()
        if not name:
            raise ValueError("name no puede estar vacío")
        
        # base_salary
        if base_salary is not None:
            if isinstance(base_salary, (list, dict, tuple)):
                raise ValueError(f"base_salary inválido: {type(base_salary).__name__}")
            try:
                base_salary = float(base_salary)
                if math.isnan(base_salary) or math.isinf(base_salary):
                    raise ValueError("base_salary no puede ser NaN o Infinito")
                if base_salary < 0:
                    raise ValueError(f"base_salary no puede ser negativo: {base_salary}")
            except (TypeError, ValueError) as e:
                raise ValueError(f"base_salary inválido: {e}")
        else:
            base_salary = 0.0
        
        # commission_rate
        if commission_rate is not None:
            if isinstance(commission_rate, (list, dict, tuple)):
                raise ValueError(f"commission_rate inválido: {type(commission_rate).__name__}")
            try:
                commission_rate = float(commission_rate)
                if math.isnan(commission_rate) or math.isinf(commission_rate):
                    raise ValueError("commission_rate no puede ser NaN o Infinito")
                if commission_rate < 0 or commission_rate > 100:
                    raise ValueError(f"commission_rate debe estar entre 0 y 100: {commission_rate}")
            except (TypeError, ValueError) as e:
                raise ValueError(f"commission_rate inválido: {e}")
        else:
            commission_rate = 0.0
        
        # loan_limit
        if loan_limit is not None:
            if isinstance(loan_limit, (list, dict, tuple)):
                raise ValueError(f"loan_limit inválido: {type(loan_limit).__name__}")
            try:
                loan_limit = float(loan_limit)
                if math.isnan(loan_limit) or math.isinf(loan_limit):
                    raise ValueError("loan_limit no puede ser NaN o Infinito")
                if loan_limit < 0:
                    raise ValueError(f"loan_limit no puede ser negativo: {loan_limit}")
            except (TypeError, ValueError) as e:
                raise ValueError(f"loan_limit inválido: {e}")
        else:
            loan_limit = 0.0
        
        employee_code = self.generate_employee_code()
        
        if not hire_date:
            hire_date = datetime.now().strftime("%Y-%m-%d")
        
        created_at = datetime.now().isoformat()
        
        employee_id = self.db.execute_write("""
            INSERT INTO employees (
                employee_code, name, position, hire_date, status,
                phone, email, base_salary, commission_rate, loan_limit,
                current_loan_balance, user_id, notes, created_at, synced
            ) VALUES (%s, %s, %s, %s, 'active', %s, %s, %s, %s, %s, 0.0, %s, %s, %s, 0)
        """, (
            employee_code, name, position, hire_date,
            phone, email, base_salary, commission_rate, loan_limit,
            user_id, notes, created_at
        ))
        
        return employee_id
    
    def get_employee(self, employee_id: int) -> Optional[Dict]:
        """Get employee by ID.
        
        Args:
            employee_id: Employee ID
            
        Returns:
            Employee dict or None
        """
        rows = self.db.execute_query("SELECT * FROM employees WHERE id = %s", (employee_id,))
        return dict(rows[0]) if rows else None
    
    def get_employee_by_code(self, employee_code: str) -> Optional[Dict]:
        """Get employee by code.
        
        Args:
            employee_code: Employee code (e.g., E001)
            
        Returns:
            Employee dict or None
        """
        rows = self.db.execute_query("SELECT * FROM employees WHERE employee_code = %s", (employee_code,))
        return dict(rows[0]) if rows else None
    
    def list_employees(self, status: str = 'active') -> List[Dict]:
        """List employees by status.
        
        Args:
            status: active, inactive, terminated, or 'all'
            
        Returns:
            List of employee dicts
        """
        if status == 'all':
            rows = self.db.execute_query("SELECT * FROM employees ORDER BY name")
        else:
            rows = self.db.execute_query("SELECT * FROM employees WHERE status = %s ORDER BY name", (status,))
        
        return [dict(row) for row in rows]
    
    def update_employee(self, employee_id: int, **kwargs) -> bool:
        """Update employee fields.
        
        Args:
            employee_id: Employee ID
            **kwargs: Fields to update
            
        Returns:
            True if updated
        """
        allowed_fields = [
            'name', 'position', 'hire_date', 'status', 'phone', 'email',
            'base_salary', 'commission_rate', 'loan_limit', 'user_id', 'notes'
        ]
        
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        
        if not updates:
            return False
        
        # SECURITY: Validar que columns están en whitelist
        ALLOWED_EMPLOYEE_COLUMNS = set(allowed_fields)
        for col in updates.keys():
            if col not in ALLOWED_EMPLOYEE_COLUMNS:
                raise ValueError(f"Columna no permitida en employees: {col}")
        
        # Build parameterized query safely (PostgreSQL uses %s)
        set_clause = ", ".join([f"{k} = %s" for k in updates.keys()])
        values = list(updates.values()) + [employee_id]

        # SECURITY: columns validadas contra whitelist
        # Add synced = 0 to mark for sync
        query = f"UPDATE employees SET {set_clause}, updated_at = CURRENT_TIMESTAMP, synced = 0 WHERE id = %s"
        rowcount = self.db.execute_write(query, tuple(values))
        
        return rowcount > 0
    
    def delete_employee(self, employee_id: int) -> bool:
        """Delete (soft delete) an employee.
        
        Args:
            employee_id: Employee ID
            
        Returns:
            True if deleted
            
        Raises:
            ValueError: If employee has outstanding loans
        """
        # Check if employee exists
        employees = self.db.execute_query("SELECT * FROM employees WHERE id = %s", (employee_id,))
        if not employees:
            raise ValueError(f"Employee {employee_id} not found")
        
        # Check for outstanding loans
        loan_counts = self.db.execute_query(
            "SELECT COUNT(*) as count FROM employee_loans WHERE employee_id = %s AND status = 'active'",
            (employee_id,)
        )
        active_loans = loan_counts[0].get('count', 0) if loan_counts and len(loan_counts) > 0 and loan_counts[0] else 0
        
        if active_loans > 0:
            raise ValueError(
                f"Cannot delete employee. {active_loans} active loan(s) outstanding. "
                "Please cancel or pay all loans first."
            )
        
        # Soft delete: set status to 'deleted'
        rowcount = self.db.execute_write(
            "UPDATE employees SET status = 'deleted', updated_at = CURRENT_TIMESTAMP, synced = 0 WHERE id = %s",
            (employee_id,)
        )
        
        return rowcount > 0
    
    # ========== LOAN MANAGEMENT ==========
    
    def calculate_installment(
        self,
        amount: Decimal,
        installments: int,
        interest_rate: float = 0.0
    ) -> Decimal:
        """Calculate installment amount with interest.

        Args:
            amount: Loan principal
            installments: Number of payments
            interest_rate: Annual interest rate percentage

        Returns:
            Installment amount per period

        Raises:
            ValueError: Si los parametros son invalidos
        """
        # Validacion de parametros
        if amount is None:
            raise ValueError("amount es requerido")
        if not isinstance(amount, Decimal):
            import decimal as decimal_module
            try:
                amount = Decimal(str(amount))
            except (decimal_module.InvalidOperation, ValueError, TypeError):
                raise ValueError(f"amount debe ser Decimal o convertible a Decimal: {amount}")
        if amount <= 0:
            raise ValueError(f"amount debe ser mayor a 0: {amount}")

        if installments is None:
            raise ValueError("installments es requerido")
        if not isinstance(installments, int) or installments <= 0:
            raise ValueError(f"installments debe ser entero positivo: {installments}")
        
        # Simple interest calculation
        # Total Interest = Principal * Rate * Time (in years)
        # Assuming monthly payments, time = installments / 12
        time_years = Decimal(installments) / Decimal(12)
        interest_amount = amount * (Decimal(str(interest_rate)) / Decimal(100)) * time_years
        
        total_amount = amount + interest_amount
        installment = total_amount / Decimal(installments)
        
        # Round to 2 decimal places
        return installment.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    def create_loan(
        self,
        employee_id: int,
        amount: float,
        loan_type: str = 'advance',
        installments: int = 1,
        interest_rate: float = 0.0,
        approved_by: int = None,
        due_date: str = None,
        notes: str = ""
    ) -> int:
        """Create a new loan or advance.
        
        Args:
            employee_id: Employee ID
            amount: Loan amount
            loan_type: 'advance' or 'loan'
            installments: Number of payments
            interest_rate: Annual interest rate percentage
            approved_by: User ID who approved
            due_date: ISO format date for full payment
            notes: Additional notes
            
        Returns:
            Loan ID
            
        Raises:
            ValueError: If validations fail
        """
        import math

        # ===== VALIDACIONES WTF =====
        if amount is None:
            raise ValueError("amount es requerido")
        if isinstance(amount, (list, dict, tuple)):
            raise ValueError(f"amount inválido: {type(amount).__name__}")
        try:
            amount = float(amount)
            if math.isnan(amount) or math.isinf(amount):
                raise ValueError("amount no puede ser NaN o Infinito")
            if amount <= 0:
                raise ValueError(f"amount debe ser mayor a 0: {amount}")
        except (TypeError, ValueError) as e:
            raise ValueError(f"amount inválido: {e}")
        
        # Validate employee exists
        employees = self.db.execute_query("SELECT * FROM employees WHERE id = %s", (employee_id,))
        if not employees:
            raise ValueError(f"Employee {employee_id} not found")
        
        employee = dict(employees[0])
        
        # Check loan limit
        current_balance = float(employee['current_loan_balance'] or 0.0)
        loan_limit = float(employee['loan_limit'] or 0.0)
        
        if current_balance + amount > loan_limit:
            raise ValueError(
                f"Loan exceeds limit. Current: ${current_balance:.2f}, "
                f"Limit: ${loan_limit:.2f}, Requested: ${amount:.2f}"
            )
        
        # Calculate installment
        installment_amount = float(self.calculate_installment(
            Decimal(str(amount)), installments, interest_rate
        ))
        
        # Set default due date if not provided
        if not due_date:
            # Default: installments months from now
            due_date = (datetime.now() + timedelta(days=30 * installments)).strftime("%Y-%m-%d")
        
        created_at = datetime.now().isoformat()
        
        # Create loan and update employee balance atomically
        operations = [
            (
                """
                INSERT INTO employee_loans (
                    employee_id, loan_type, amount, balance, interest_rate,
                    installments, installment_amount, status, approved_by,
                    created_at, due_date, notes, synced
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'active', %s, %s, %s, %s, 0)
                """,
                (
                    employee_id, loan_type, amount, amount, interest_rate,
                    installments, installment_amount, approved_by,
                    created_at, due_date, notes
                )
            ),
            (
                "UPDATE employees SET current_loan_balance = %s, updated_at = CURRENT_TIMESTAMP, synced = 0 WHERE id = %s",
                (current_balance + amount, employee_id)
            )
        ]

        self.db.execute_transaction(operations)
        
        # Get the loan ID (for PostgreSQL, we need to query it)
        # For SQLite, lastrowid works, but for PostgreSQL we need to query
        loans = self.db.execute_query(
            "SELECT id FROM employee_loans WHERE employee_id = %s AND created_at = %s ORDER BY id DESC LIMIT 1",
            (employee_id, created_at)
        )
        loan_id = loans[0].get('id') if loans and len(loans) > 0 and loans[0] else None

        return loan_id
    
    def get_loan(self, loan_id: int) -> Optional[Dict]:
        """Get loan by ID.
        
        Args:
            loan_id: Loan ID
            
        Returns:
            Loan dict or None
        """
        rows = self.db.execute_query("SELECT * FROM employee_loans WHERE id = %s", (loan_id,))
        return dict(rows[0]) if rows else None
    
    def list_loans(
        self,
        employee_id: int = None,
        status: str = 'active'
    ) -> List[Dict]:
        """List loans, optionally filtered by employee and status.
        
        Args:
            employee_id: Filter by employee (optional)
            status: Filter by status (active, paid, cancelled, or 'all')
            
        Returns:
            List of loan dicts
        """
        if employee_id and status != 'all':
            rows = self.db.execute_query(
                "SELECT * FROM employee_loans WHERE employee_id = %s AND status = %s ORDER BY created_at DESC",
                (employee_id, status)
            )
        elif employee_id:
            rows = self.db.execute_query(
                "SELECT * FROM employee_loans WHERE employee_id = %s ORDER BY created_at DESC",
                (employee_id,)
            )
        elif status != 'all':
            rows = self.db.execute_query(
                "SELECT * FROM employee_loans WHERE status = %s ORDER BY created_at DESC",
                (status,)
            )
        else:
            rows = self.db.execute_query("SELECT * FROM employee_loans ORDER BY created_at DESC")
        
        return [dict(row) for row in rows]
    
    def cancel_loan(
        self,
        loan_id: int,
        user_id: int,
        reason: str = ""
    ) -> bool:
        """Cancel an active loan.
        
        Args:
            loan_id: Loan ID
            user_id: User cancelling the loan
            reason: Reason for cancellation
            
        Returns:
            True if cancelled
            
        Raises:
            ValueError: If loan cannot be cancelled
        """
        # Get loan
        loans = self.db.execute_query("SELECT * FROM employee_loans WHERE id = %s", (loan_id,))
        if not loans:
            raise ValueError(f"Loan {loan_id} not found")
        
        loan = dict(loans[0])
        if loan.get('status') != 'active':
            raise ValueError(f"Can only cancel active loans. Current status: {loan.get('status')}")
        
        # Update loan status and employee balance atomically
        operations = [
            (
                "UPDATE employee_loans SET status = 'cancelled', notes = %s, updated_at = CURRENT_TIMESTAMP, synced = 0 WHERE id = %s",
                (f"Cancelled by user {user_id}. Reason: {reason}", loan_id)
            ),
            (
                "UPDATE employees SET current_loan_balance = current_loan_balance - %s, updated_at = CURRENT_TIMESTAMP, synced = 0 WHERE id = %s",
                (loan.get('balance', 0), loan.get('employee_id'))
            )
        ]

        self.db.execute_transaction(operations)
        return True
    
    # ========== PAYMENT PROCESSING ==========
    
    def record_payment(
        self,
        loan_id: int,
        amount: float,
        payment_type: str = 'manual',
        user_id: int = None,
        sale_id: int = None,
        notes: str = ""
    ) -> int:
        """Record a payment against a loan.
        
        Args:
            loan_id: Loan ID
            amount: Payment amount
            payment_type: manual, commission_deduct, payroll_deduct
            user_id: User recording the payment
            sale_id: Related sale ID (for commission deductions)
            notes: Additional notes
            
        Returns:
            Payment ID
            
        Raises:
            ValueError: If payment is invalid
        """
        # Get loan
        loans = self.db.execute_query("SELECT * FROM employee_loans WHERE id = %s", (loan_id,))
        if not loans:
            raise ValueError(f"Loan {loan_id} not found")
        
        loan = dict(loans[0])
        if loan.get('status') not in ('active',):
            raise ValueError(f"Cannot pay {loan.get('status')} loan")
        
        if amount <= 0:
            raise ValueError("Payment amount must be positive")

        current_balance = float(loan.get('balance', 0))
        if amount > current_balance:
            raise ValueError(f"Payment ${amount:.2f} exceeds balance ${current_balance:.2f}")
        
        # Calculate new balance
        new_balance = current_balance - amount
        payment_date = datetime.now().isoformat()
        
        # Build operations for atomic transaction
        operations = [
            (
                """
                INSERT INTO loan_payments (
                    loan_id, amount, payment_type, payment_date,
                    sale_id, user_id, balance_after, notes
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    loan_id, amount, payment_type, payment_date,
                    sale_id, user_id, new_balance, notes
                )
            ),
            (
                "UPDATE employee_loans SET balance = %s, updated_at = CURRENT_TIMESTAMP, synced = 0 WHERE id = %s",
                (new_balance, loan_id)
            )
        ]

        # If fully paid, mark as paid
        if new_balance < 0.01:  # Account for floating point precision
            operations.append((
                "UPDATE employee_loans SET status = 'paid', paid_at = %s, updated_at = CURRENT_TIMESTAMP, synced = 0 WHERE id = %s",
                (payment_date, loan_id)
            ))
        
        # Update employee balance
        operations.append((
            "UPDATE employees SET current_loan_balance = current_loan_balance - %s, updated_at = CURRENT_TIMESTAMP, synced = 0 WHERE id = %s",
            (amount, loan['employee_id'])
        ))

        # Execute all operations atomically
        self.db.execute_transaction(operations)
        
        # Get payment ID (for PostgreSQL compatibility)
        payments = self.db.execute_query(
            "SELECT id FROM loan_payments WHERE loan_id = %s AND payment_date = %s ORDER BY id DESC LIMIT 1",
            (loan_id, payment_date)
        )
        payment_id = payments[0].get('id') if payments and len(payments) > 0 and payments[0] else None

        return payment_id
    
    def get_payment_history(self, loan_id: int) -> List[Dict]:
        """Get payment history for a loan.
        
        Args:
            loan_id: Loan ID
            
        Returns:
            List of payment dicts
        """
        rows = self.db.execute_query(
            "SELECT * FROM loan_payments WHERE loan_id = %s ORDER BY payment_date DESC",
            (loan_id,)
        )
        return [dict(row) for row in rows]
    
    def deduct_from_commission(
        self,
        employee_id: int,
        commission_amount: float,
        sale_id: int,
        user_id: int
    ) -> Decimal:
        """Automatically deduct loan payments from employee commission.
        
        Args:
            employee_id: Employee ID
            commission_amount: Total commission earned
            sale_id: Sale ID
            user_id: User ID processing the sale
            
        Returns:
            Net commission after deductions
        """
        # Get active loans for employee
        loans = self.db.execute_query(
            "SELECT * FROM employee_loans WHERE employee_id = %s AND status = 'active' ORDER BY created_at",
            (employee_id,)
        )
        
        remaining_commission = Decimal(str(commission_amount))
        
        for loan_row in loans:
            loan = dict(loan_row)
            if remaining_commission <= 0:
                break
            
            installment = Decimal(str(loan['installment_amount']))
            balance = Decimal(str(loan['balance']))
            
            # Deduct the lesser of: installment amount, remaining balance, or available commission
            deduction = min(installment, balance, remaining_commission)
            
            if deduction > 0:
                # Record payment
                self.record_payment(
                    loan_id=loan['id'],
                    amount=float(deduction),
                    payment_type='commission_deduct',
                    user_id=user_id,
                    sale_id=sale_id,
                    notes=f"Auto-deducted from sale #{sale_id}"
                )
                
                remaining_commission -= deduction
        
        return remaining_commission
    
    # ========== REPORTING ==========
    
    def get_employee_loan_summary(self, employee_id: int) -> Dict:
        """Get loan summary for an employee.
        
        Args:
            employee_id: Employee ID
            
        Returns:
            Summary dict with totals and stats
        """
        employees = self.db.execute_query("SELECT * FROM employees WHERE id = %s", (employee_id,))
        if not employees:
            return {}
        
        employee = dict(employees[0])
        
        # Get loan stats
        stats_rows = self.db.execute_query("""
            SELECT 
                COUNT(*) as total_loans,
                SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active_loans,
                SUM(CASE WHEN status = 'paid' THEN 1 ELSE 0 END) as paid_loans,
                SUM(CASE WHEN status = 'active' THEN amount ELSE 0 END) as total_active_amount,
                SUM(CASE WHEN status = 'active' THEN balance ELSE 0 END) as total_balance,
                SUM(CASE WHEN status = 'paid' THEN amount ELSE 0 END) as total_paid_amount
            FROM employee_loans
            WHERE employee_id = %s
        """, (employee_id,))
        
        stats = dict(stats_rows[0]) if stats_rows else {}
        
        return {
            'employee_id': employee_id,
            'employee_name': employee['name'],
            'employee_code': employee['employee_code'],
            'loan_limit': float(employee['loan_limit'] or 0.0),
            'current_balance': float(employee['current_loan_balance'] or 0.0),
            'total_loans': stats.get('total_loans', 0) or 0,
            'active_loans': stats.get('active_loans', 0) or 0,
            'paid_loans': stats.get('paid_loans', 0) or 0,
            'total_active_amount': float(stats['total_active_amount'] or 0.0),
            'total_balance': float(stats['total_balance'] or 0.0),
            'total_paid_amount': float(stats['total_paid_amount'] or 0.0)
        }
    
    def get_outstanding_loans(self) -> List[Dict]:
        """Get all outstanding loans across all employees.
        
        Returns:
            List of loan dicts with employee info
        """
        rows = self.db.execute_query("""
            SELECT 
                l.*,
                e.name as employee_name,
                e.employee_code
            FROM employee_loans l
            JOIN employees e ON l.employee_id = e.id
            WHERE l.status = 'active'
            ORDER BY l.created_at DESC
        """)
        
        return [dict(row) for row in rows]
    
    def get_overdue_loans(self) -> List[Dict]:
        """Get loans past their due date.
        
        Returns:
            List of overdue loan dicts with employee info
        """
        today = datetime.now().strftime("%Y-%m-%d")
        
        rows = self.db.execute_query("""
            SELECT 
                l.*,
                e.name as employee_name,
                e.employee_code,
                e.phone as employee_phone
            FROM employee_loans l
            JOIN employees e ON l.employee_id = e.id
            WHERE l.status = 'active' AND l.due_date < %s
            ORDER BY l.due_date
        """, (today,))
        
        return [dict(row) for row in rows]
