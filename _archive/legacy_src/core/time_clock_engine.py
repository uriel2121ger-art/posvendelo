"""
Time Clock Engine - Employee Attendance Management
Handles check-in/out, breaks, hours calculation, and reporting
"""

from typing import Dict, List, Optional, Tuple, TYPE_CHECKING
from datetime import datetime
from datetime import time as dt_time
from datetime import timedelta
from decimal import Decimal
import json
from pathlib import Path
import logging

if TYPE_CHECKING:
    from src.infra.database import DatabaseManager

logger = logging.getLogger(__name__)


class TimeClockEngine:
    """Engine for managing employee attendance and time tracking."""
    
    # Default attendance rules
    DEFAULT_RULES = {
        'standard_start_time': '08:00',
        'standard_end_time': '17:00',
        'daily_hours_target': 8,
        'weekly_hours_target': 40,
        'grace_period_minutes': 15,
        'daily_overtime_threshold': 8,
        'weekly_overtime_threshold': 40,
        'overtime_multiplier': 1.5,
        'max_break_duration_minutes': 60,
        'max_daily_hours': 12,
    }
    
    def __init__(self, db_manager: "DatabaseManager"):
        """Initialize Time Clock Engine.
        
        Args:
            db_manager: DatabaseManager instance (supports SQLite and PostgreSQL)
        """
        self.db = db_manager
        self.rules = self._load_rules()
    
    def _load_rules(self) -> Dict:
        """Load attendance rules from database or use defaults."""
        try:
            rows = self.db.execute_query("""
                SELECT rule_name, work_start_time, work_end_time, late_tolerance_minutes, overtime_after_hours
                FROM attendance_rules 
                WHERE is_active = 1
            """)
            
            rules = dict(self.DEFAULT_RULES)
            for row in rows:
                row_dict = dict(row)
                rule_name = row_dict.get('rule_name', '')
                if rule_name:
                    # Build rule data from individual columns
                    rule_data = {
                        rule_name: {
                            'work_start_time': row_dict.get('work_start_time'),
                            'work_end_time': row_dict.get('work_end_time'),
                            'late_tolerance_minutes': row_dict.get('late_tolerance_minutes', 15),
                            'overtime_after_hours': row_dict.get('overtime_after_hours', 8.0)
                        }
                    }
                    rules.update(rule_data)
            
            return rules
            
        except Exception as e:
            logger.debug(f"Error loading attendance rules, using defaults: {e}")
            return dict(self.DEFAULT_RULES)

    def save_rules(self, rules: Dict) -> bool:
        """Save attendance rules."""
        try:
            # Note: CREATE TABLE IF NOT EXISTS should be in schema_postgresql.sql
            # For PostgreSQL, we need to use INSERT ... ON CONFLICT instead of INSERT OR REPLACE
            timestamp = datetime.now().isoformat()
            
            # PostgreSQL: Use ON CONFLICT, SQLite: Use INSERT OR REPLACE
            # QueryConverter will handle this, but we need to check backend type
            from src.infra.database_central import PostgreSQLBackend
            
            if isinstance(self.db.backend, PostgreSQLBackend):
                # PostgreSQL syntax
                self.db.execute_write("""
                    INSERT INTO attendance_rules 
                    (rule_name, rule_type, value_json, is_active, created_at, updated_at)
                    VALUES (%s, %s, %s, 1, %s, %s)
                    ON CONFLICT (rule_name) DO UPDATE SET
                        value_json = EXCLUDED.value_json,
                        updated_at = EXCLUDED.updated_at,
                        is_active = EXCLUDED.is_active
                """, ('general', 'general', json.dumps(rules), timestamp, timestamp))
            else:
                # SQLite syntax
                self.db.execute_write("""
                    INSERT INTO attendance_rules 
                    (rule_name, rule_type, value_json, is_active, created_at, updated_at)
                    VALUES (%s, %s, %s, 1, %s, %s)
                """, ('general', 'general', json.dumps(rules), timestamp, timestamp))
            
            # Reload rules
            self.rules = self._load_rules()
            return True
            
        except Exception as e:
            logger.error(f"Error saving rules: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # ==================== CHECK IN/OUT ====================
    
    def check_in(
        self,
        employee_id: int,
        user_id: int,
        location: str = "POS Terminal",
        notes: Optional[str] = None,
        timestamp: Optional[str] = None
    ) -> Dict:
        """
        Register employee check-in.
        
        Args:
            employee_id: ID of employee
            user_id: ID of user registering (admin or employee)
            location: Location of check-in
            notes: Optional notes
            timestamp: Optional specific timestamp (for manual entry)
        
        Returns:
            {
                'entry_id': int,
                'employee_id': int,
                'employee_name': str,
                'check_in_time': str,
                'is_late': bool,
                'late_minutes': int,
                'scheduled_start': str
            }
        """
        # Get employee info
        employees = self.db.execute_query("SELECT name FROM employees WHERE id = %s", (employee_id,))
        if not employees or len(employees) == 0 or not employees[0]:
            raise ValueError(f"Employee {employee_id} not found")

        employee = dict(employees[0])

        # Check if already checked in today
        today = datetime.now().date().isoformat()
        existing_entries = self.db.execute_query("""
            SELECT id FROM time_clock_entries 
            WHERE employee_id = %s 
            AND CAST(timestamp AS DATE) = CAST(%s AS DATE)
            AND entry_type = 'check_in'
            ORDER BY timestamp DESC LIMIT 1
        """, (employee_id, today))
        
        if existing_entries and len(existing_entries) > 0 and existing_entries[0]:
            existing_id = existing_entries[0].get('id')
            # Check if already checked out
            checkout_entries = self.db.execute_query("""
                SELECT id FROM time_clock_entries
                WHERE employee_id = %s
                AND CAST(timestamp AS DATE) = CAST(%s AS DATE)
                AND entry_type = 'check_out'
                AND timestamp > (
                    SELECT timestamp FROM time_clock_entries
                    WHERE id = %s
                )
            """, (employee_id, today, existing_id))
            
            if not checkout_entries:
                raise ValueError("Employee already checked in. Must check out first.")
        
        # Create check-in entry
        check_in_time = timestamp or datetime.now().isoformat()
        is_manual = 1 if timestamp else 0
        
        entry_id = self.db.execute_write("""
            INSERT INTO time_clock_entries (
                employee_id, entry_type, timestamp, location,
                notes, user_id, is_manual, created_at
            ) VALUES (%s, 'check_in', %s, %s, %s, %s, %s, %s)
        """, (employee_id, check_in_time, location, notes, user_id, is_manual, datetime.now().isoformat()))
        
        # Check for tardiness
        check_in_dt = datetime.fromisoformat(check_in_time)
        scheduled_start = self._get_schedule_start(employee_id, check_in_dt.date())
        
        is_late, late_minutes = self._calculate_tardiness(check_in_dt, scheduled_start)
        
        return {
            'entry_id': entry_id,
            'employee_id': employee_id,
            'employee_name': employee['name'],
            'check_in_time': check_in_time,
            'is_late': is_late,
            'late_minutes': late_minutes,
            'scheduled_start': scheduled_start.isoformat() if scheduled_start else None
        }
    
    def check_out(
        self,
        employee_id: int,
        user_id: int,
        notes: Optional[str] = None,
        timestamp: Optional[str] = None
    ) -> Dict:
        """
        Register employee check-out.
        
        Returns:
            {
                'entry_id': int,
                'employee_id': int,
                'employee_name': str,
                'check_in_time': str,
                'check_out_time': str,
                'total_hours': Decimal,
                'regular_hours': Decimal,
                'overtime_hours': Decimal,
                'break_minutes': int
            }
        """
        # Get employee info
        employees = self.db.execute_query("SELECT name FROM employees WHERE id = %s", (employee_id,))
        if not employees:
            raise ValueError(f"Employee {employee_id} not found")
        
        employee = dict(employees[0])
        
        # Find latest unclosed check-in
        today = datetime.now().date().isoformat()
        check_in_entries = self.db.execute_query("""
            SELECT id, timestamp FROM time_clock_entries
            WHERE employee_id = %s
            AND CAST(timestamp AS DATE) = CAST(%s AS DATE)
            AND entry_type = 'check_in'
            AND id NOT IN (
                SELECT entry_id FROM time_clock_entries co
                WHERE co.employee_id = %s 
                AND co.entry_type = 'check_out'
                AND CAST(co.timestamp AS DATE) = CAST(%s AS DATE)
            )
            ORDER BY timestamp DESC LIMIT 1
        """, (employee_id, today, employee_id, today))
        
        if not check_in_entries:
            raise ValueError("No active check-in found for today")
        
        check_in_entry = dict(check_in_entries[0])
        
        # Create check-out entry
        check_out_time = timestamp or datetime.now().isoformat()
        is_manual = 1 if timestamp else 0
        
        entry_id = self.db.execute_write("""
            INSERT INTO time_clock_entries (
                employee_id, entry_type, timestamp, location,
                notes, user_id, is_manual, created_at
            ) VALUES (%s, 'check_out', %s, NULL, %s, %s, %s, %s)
        """, (employee_id, check_out_time, notes, user_id, is_manual, datetime.now().isoformat()))
        
        # Calculate hours and breaks
        try:
            check_in_dt = datetime.fromisoformat(str(check_in_entry['timestamp']))
        except (ValueError, TypeError):
            check_in_dt = datetime.now()
            logger.warning(f"Invalid check_in timestamp for employee {employee_id}, using current time")
        check_out_dt = datetime.fromisoformat(check_out_time)
        
        # Get total break time
        break_rows = self.db.execute_query("""
            SELECT COALESCE(SUM(duration_minutes), 0) as total_break_minutes
            FROM breaks
            WHERE employee_id = %s
            AND CAST(break_start AS DATE) = CAST(%s AS DATE)
            AND break_end IS NOT NULL
        """, (employee_id, check_in_dt.date().isoformat()))

        break_minutes = break_rows[0].get('total_break_minutes', 0) if break_rows and len(break_rows) > 0 and break_rows[0] else 0

        # Calculate hours
        regular_hours, overtime_hours = self.calculate_hours(
            check_in_dt, check_out_dt, break_minutes
        )
        total_hours = regular_hours + overtime_hours
        
        # Update or create attendance summary
        self._update_attendance_summary(
            employee_id,
            check_in_dt.date().isoformat(),
            check_in_dt.time().isoformat(),
            check_out_dt.time().isoformat(),
            float(total_hours),
            float(regular_hours),
            float(overtime_hours),
            break_minutes
        )
        
        return {
            'entry_id': entry_id,
            'employee_id': employee_id,
            'employee_name': employee['name'],
            'check_in_time': check_in_entry['timestamp'],
            'check_out_time': check_out_time,
            'total_hours': total_hours,
            'regular_hours': regular_hours,
            'overtime_hours': overtime_hours,
            'break_minutes': break_minutes
        }
    
    def get_current_status(self, employee_id: int) -> Dict:
        """
        Get employee's current status.
        
        Returns:
            {
                'employee_id': int,
                'is_checked_in': bool,
                'check_in_time': str,
                'hours_worked': Decimal,
                'on_break': bool,
                'break_start': str,
                'break_duration_minutes': int
            }
        """
        today = datetime.now().date().isoformat()
        
        # Check for active check-in
        check_ins = self.db.execute_query("""
            SELECT id, timestamp FROM time_clock_entries
            WHERE employee_id = %s
            AND CAST(timestamp AS DATE) = CAST(%s AS DATE)
            AND entry_type = 'check_in'
            AND id NOT IN (
                SELECT entry_id FROM time_clock_entries co
                WHERE co.employee_id = %s 
                AND co.entry_type = 'check_out'
                AND CAST(co.timestamp AS DATE) = CAST(%s AS DATE)
                AND co.timestamp > time_clock_entries.timestamp
            )
            ORDER BY timestamp DESC LIMIT 1
        """, (employee_id, today, employee_id, today))
        
        if not check_ins:
            return {
                'employee_id': employee_id,
                'is_checked_in': False,
                'check_in_time': None,
                'hours_worked': Decimal('0'),
                'on_break': False,
                'break_start': None,
                'break_duration_minutes': 0
            }
        
        check_in = dict(check_ins[0])
        check_in_timestamp = check_in.get('timestamp')
        if not check_in_timestamp:
            return {
                'employee_id': employee_id,
                'is_checked_in': False,
                'check_in_time': None,
                'hours_worked': Decimal('0'),
                'on_break': False,
                'break_start': None,
                'break_duration_minutes': 0
            }
        check_in_time = datetime.fromisoformat(check_in_timestamp)
        hours_worked = Decimal(str((datetime.now() - check_in_time).total_seconds() / 3600))
        
        # Check for active break
        active_breaks = self.db.execute_query("""
            SELECT id, break_start FROM breaks
            WHERE employee_id = %s
            AND CAST(break_start AS DATE) = CAST(%s AS DATE)
            AND break_end IS NULL
            ORDER BY break_start DESC LIMIT 1
        """, (employee_id, today))
       
        active_break = dict(active_breaks[0]) if active_breaks else None
        
        on_break = active_break is not None
        break_start = active_break['break_start'] if active_break else None
        break_duration = 0
        
        if on_break and break_start:
            break_start_dt = datetime.fromisoformat(break_start)
            break_duration = int((datetime.now() - break_start_dt).total_seconds() / 60)

        return {
            'employee_id': employee_id,
            'is_checked_in': True,
            'check_in_time': check_in['timestamp'],
            'hours_worked': hours_worked,
            'on_break': on_break,
            'break_start': break_start,
            'break_duration_minutes': break_duration
        }
    
    # ==================== BREAKS ====================
    
    def start_break(
        self,
        employee_id: int,
        break_type: str = 'regular',
        notes: Optional[str] = None
    ) -> int:
        """Start a break for employee."""
        # Verify employee is checked in
        status = self.get_current_status(employee_id)
        if not status['is_checked_in']:
            raise ValueError("Employee must be checked in to start break")
        
        if status['on_break']:
            raise ValueError("Employee is already on break")
        
        # Get today's check-in entry
        today = datetime.now().date().isoformat()
        entries = self.db.execute_query("""
            SELECT id FROM time_clock_entries
            WHERE employee_id = %s
            AND CAST(timestamp AS DATE) = CAST(%s AS DATE)
            AND entry_type = 'check_in'
            ORDER BY timestamp DESC LIMIT 1
        """, (employee_id, today))
        
        if not entries:
            raise ValueError("No check-in entry found")
        
        entry = dict(entries[0])
        
        # Create break record
        break_start = datetime.now().isoformat()
        break_id = self.db.execute_write("""
            INSERT INTO breaks (
                employee_id, entry_id, break_start, break_type, notes, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """, (employee_id, entry['id'], break_start, break_type, notes, datetime.now().isoformat()))
        
        return break_id
    
    def end_break(self, employee_id: int) -> Dict:
        """End current break."""
        # Find active break
        today = datetime.now().date().isoformat()
        active_breaks = self.db.execute_query("""
            SELECT id, break_start, break_type FROM breaks
            WHERE employee_id = %s
            AND CAST(break_start AS DATE) = CAST(%s AS DATE)
            AND break_end IS NULL
            ORDER BY break_start DESC LIMIT 1
        """, (employee_id, today))
        
        if not active_breaks:
            raise ValueError("No active break found")
        
        active_break = dict(active_breaks[0])
        
        # Calculate duration and end break
        break_end = datetime.now().isoformat()
        break_start_dt = datetime.fromisoformat(active_break['break_start'])
        break_end_dt = datetime.fromisoformat(break_end)
        duration_minutes = int((break_end_dt - break_start_dt).total_seconds() / 60)
        
        self.db.execute_write("""
            UPDATE breaks
            SET break_end = %s, duration_minutes = %s
            WHERE id = %s
        """, (break_end, duration_minutes, active_break['id']))
        
        return {
            'break_id': active_break['id'],
            'duration_minutes': duration_minutes,
            'break_type': active_break['break_type']
        }
    
    # ==================== CALCULATIONS ====================
    
    def calculate_hours(
        self,
        check_in: datetime,
        check_out: datetime,
        break_minutes: int = 0
    ) -> Tuple[Decimal, Decimal]:
        """
        Calculate regular and overtime hours.
        
        Returns:
            (regular_hours, overtime_hours)
        """
        # Total time minus breaks
        total_seconds = (check_out - check_in).total_seconds()
        total_seconds -= (break_minutes * 60)
        total_hours = Decimal(str(total_seconds / 3600))
        
        daily_threshold = Decimal(str(self.rules['daily_overtime_threshold']))
        
        if total_hours <= daily_threshold:
            return (total_hours, Decimal('0'))
        else:
            regular = daily_threshold
            overtime = total_hours - daily_threshold
            return (regular, overtime)
    
    # Additional methods truncated for brevity...
    # Include: _calculate_tardiness, _get_schedule_start, _update_attendance_summary,
    # get_daily_attendance, get_employee_history, etc.
    
    def _calculate_tardiness(
        self,
        check_in: datetime,
        scheduled_start: Optional[datetime]
    ) -> Tuple[bool, int]:
        """Calculate if employee is late and by how many minutes."""
        if not scheduled_start:
            return (False, 0)
        
        late_seconds = (check_in - scheduled_start).total_seconds()
        late_minutes = int(late_seconds / 60)
        
        grace_period = self.rules['grace_period_minutes']
        
        if late_minutes <= grace_period:
            return (False, 0)
        
        return (True, late_minutes - grace_period)
    
    def _get_schedule_start(self, employee_id: int, date) -> Optional[datetime]:
        """Get scheduled start time for employee on given date."""
        # For now, use default rule
        # In future, can have employee-specific schedules
        start_time_str = self.rules['standard_start_time']
        # FIX 2026-02-01: Safely parse time string with validation
        try:
            parts = start_time_str.split(':')
            if len(parts) >= 2:
                hour = int(parts[0])
                minute = int(parts[1])
                # Validate hour and minute ranges
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    return datetime.combine(date, dt_time(hour, minute))
        except (ValueError, TypeError, AttributeError):
            pass
        # Default to 8:00 AM if parsing fails
        return datetime.combine(date, dt_time(8, 0))
    
    def _update_attendance_summary(
        self,
        employee_id: int,
        date: str,
        check_in_time: str,
        check_out_time: str,
        total_hours: float,
        regular_hours: float,
        overtime_hours: float,
        break_minutes: int
    ):
        """Update or create attendance summary record."""
        # Check tardiness
        check_in_dt = datetime.fromisoformat(f"{date}T{check_in_time}")
        scheduled_start = self._get_schedule_start(employee_id, check_in_dt.date())
        is_late, late_minutes = self._calculate_tardiness(check_in_dt, scheduled_start)
        
        # PostgreSQL: Use ON CONFLICT, SQLite: Use INSERT OR REPLACE
        from src.infra.database_central import PostgreSQLBackend
        
        if isinstance(self.db.backend, PostgreSQLBackend):
            # PostgreSQL syntax
            self.db.execute_write("""
                INSERT INTO attendance_summary (
                    employee_id, date, check_in_time, check_out_time,
                    total_hours, regular_hours, overtime_hours, break_minutes,
                    was_late, late_minutes, status, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'present', %s)
                ON CONFLICT (employee_id, date) DO UPDATE SET
                    check_in_time = EXCLUDED.check_in_time,
                    check_out_time = EXCLUDED.check_out_time,
                    total_hours = EXCLUDED.total_hours,
                    regular_hours = EXCLUDED.regular_hours,
                    overtime_hours = EXCLUDED.overtime_hours,
                    break_minutes = EXCLUDED.break_minutes,
                    was_late = EXCLUDED.was_late,
                    late_minutes = EXCLUDED.late_minutes,
                    status = EXCLUDED.status
            """, (
                employee_id, date, check_in_time, check_out_time,
                total_hours, regular_hours, overtime_hours, break_minutes,
                1 if is_late else 0, late_minutes, datetime.now().isoformat()
            ))
        else:
            # PostgreSQL syntax (ON CONFLICT) - fallback si no detecta backend
            self.db.execute_write("""
                INSERT INTO attendance_summary (
                    employee_id, date, check_in_time, check_out_time,
                    total_hours, regular_hours, overtime_hours, break_minutes,
                    was_late, late_minutes, status, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'present', %s)
                ON CONFLICT (employee_id, date) DO UPDATE SET
                    check_in_time = EXCLUDED.check_in_time,
                    check_out_time = EXCLUDED.check_out_time,
                    total_hours = EXCLUDED.total_hours,
                    regular_hours = EXCLUDED.regular_hours,
                    overtime_hours = EXCLUDED.overtime_hours,
                    break_minutes = EXCLUDED.break_minutes,
                    was_late = EXCLUDED.was_late,
                    late_minutes = EXCLUDED.late_minutes,
                    status = EXCLUDED.status
            """, (
                employee_id, date, check_in_time, check_out_time,
                total_hours, regular_hours, overtime_hours, break_minutes,
                1 if is_late else 0, late_minutes, datetime.now().isoformat()
            ))
    
    # ==================== REPORTING ====================
    
    def get_daily_attendance(self, date_str: str) -> List[Dict]:
        """Get attendance for a specific date with real-time updates."""
        # Get all employees who have entries on this date
        employees = self.db.execute_query("""
            SELECT DISTINCT e.id, e.employee_code, e.name
            FROM employees e
            LEFT JOIN time_clock_entries tce ON e.id = tce.employee_id
            WHERE e.is_active = 1
            AND (CAST(tce.timestamp AS DATE) = CAST(%s AS DATE) OR tce.id IS NULL)
            ORDER BY e.employee_code
        """, (date_str,))
            
        result = []
        now = datetime.now()
        
        for row in employees:
            row_dict = dict(row)
            employee_id = row_dict['id']
            
            # Get check-in for this date
            check_ins = self.db.execute_query("""
                SELECT timestamp FROM time_clock_entries
                WHERE employee_id = %s
                AND CAST(timestamp AS DATE) = CAST(%s AS DATE)
                AND entry_type = 'check_in'
                ORDER BY timestamp DESC LIMIT 1
            """, (employee_id, date_str))
            
            if not check_ins:
                continue  # Skip if no check-in today

            check_in_time = check_ins[0].get('timestamp') if check_ins[0] else None
            if not check_in_time:
                continue

            # Get check-out
            check_outs = self.db.execute_query("""
                SELECT timestamp FROM time_clock_entries
                WHERE employee_id = %s
                AND CAST(timestamp AS DATE) = CAST(%s AS DATE)
                AND entry_type = 'check_out'
                AND timestamp > %s
                ORDER BY timestamp DESC LIMIT 1
            """, (employee_id, date_str, check_in_time))
            
            check_out_time = check_outs[0].get('timestamp') if check_outs and len(check_outs) > 0 and check_outs[0] else None

            # Calculate hours
            check_in_dt = datetime.fromisoformat(check_in_time)
            if check_out_time:
                check_out_dt = datetime.fromisoformat(check_out_time)
                is_checked_in = False
            else:
                check_out_dt = now
                is_checked_in = True
            
            # Get breaks
            break_rows = self.db.execute_query("""
                SELECT COALESCE(SUM(duration_minutes), 0) as total_break_minutes
                FROM breaks
                WHERE employee_id = %s
                AND CAST(break_start AS DATE) = CAST(%s AS DATE)
                AND break_end IS NOT NULL
            """, (employee_id, date_str))
            
            break_minutes = break_rows[0].get('total_break_minutes', 0) if break_rows and len(break_rows) > 0 and break_rows[0] else 0

            # Calculate hours
            total_seconds = (check_out_dt - check_in_dt).total_seconds()
            total_seconds -= (break_minutes * 60)
            hours_worked = Decimal(str(total_seconds / 3600)) if total_seconds > 0 else Decimal('0')
            
            # Check for active break
            active_breaks = self.db.execute_query("""
                SELECT id FROM breaks
                WHERE employee_id = %s
                AND CAST(break_start AS DATE) = CAST(%s AS DATE)
                AND break_end IS NULL
            """, (employee_id, date_str))
            
            on_break = len(active_breaks) > 0
            
            # Check tardiness
            scheduled_start = self._get_schedule_start(employee_id, check_in_dt.date())
            was_late, late_minutes = self._calculate_tardiness(check_in_dt, scheduled_start)
            
            result.append({
                'employee_id': employee_id,
                'employee_code': row_dict['employee_code'],
                'employee_name': row_dict['name'],
                'check_in_time': check_in_time,
                'check_out_time': check_out_time,
                'hours_worked': hours_worked,
                'break_minutes': break_minutes,
                'is_checked_in': is_checked_in,
                'on_break': on_break,
                'was_late': was_late,
                'late_minutes': late_minutes
            })
        
        return result

    def get_attendance_range(self, start_date: str, end_date: str) -> List[Dict]:
        """Get attendance summary list for a date range."""
        rows = self.db.execute_query("""
            SELECT 
                a.*,
                e.name as employee_name,
                e.employee_code
            FROM attendance_summary a
            JOIN employees e ON a.employee_id = e.id
            WHERE a.date BETWEEN %s AND %s
            ORDER BY a.date DESC, e.name ASC
        """, (start_date, end_date))
        
        return [dict(row) for row in rows]
