#!/usr/bin/env python3
"""
Error Tracker for TITAN POS
Tracks errors and generates reports
"""

from collections import defaultdict
from datetime import datetime, timedelta
import json
from pathlib import Path
import sys
import traceback


class ErrorTracker:
    """Track and analyze errors."""
    
    def __init__(self, error_log="logs/errors.jsonl"):
        self.error_log = Path(error_log)
        self.error_log.parent.mkdir(exist_ok=True)
        self.errors = []
    
    def log_error(self, exception, context=None):
        """Log an error with context."""
        error_data = {
            'timestamp': datetime.now().isoformat(),
            'type': type(exception).__name__,
            'message': str(exception),
            'traceback': ''.join(traceback.format_exception(
                type(exception), exception, exception.__traceback__
            )),
            'context': context or {}
        }
        
        self.errors.append(error_data)
        
        # Append to log file
        with open(self.error_log, 'a') as f:
            f.write(json.dumps(error_data) + '\n')
        
        # Print to console
        print(f"❌ ERROR: {error_data['type']}: {error_data['message']}")
    
    def get_error_summary(self, days=None):
        """Get error summary statistics."""
        # Load errors from file
        if self.error_log.exists():
            with open(self.error_log) as f:
                all_errors = [json.loads(line) for line in f]
        else:
            all_errors = self.errors
        
        # Filter by date if specified
        if days:
            cutoff = (datetime.now() - timedelta(days=days)).isoformat()
            all_errors = [e for e in all_errors if e['timestamp'] >= cutoff]
        
        # Group by error type
        by_type = defaultdict(list)
        for error in all_errors:
            by_type[error['type']].append(error)
        
        # Generate summary
        summary = {
            'total_errors': len(all_errors),
            'unique_types': len(by_type),
            'by_type': {
                error_type: {
                    'count': len(errors),
                    'latest': errors[-1]['timestamp'],
                    'message': errors[0]['message']
                }
                for error_type, errors in sorted(
                    by_type.items(),
                    key=lambda x: len(x[1]),
                    reverse=True
                )
            }
        }
        
        return summary
    
    def print_report(self, days=None):
        """Print error report."""
        summary = self.get_error_summary(days)
        
        print("=" * 80)
        print("ERROR TRACKING REPORT")
        print("=" * 80)
        print(f"Period: {'Last ' + str(days) + ' days' if days else 'All time'}")
        print(f"Total Errors: {summary['total_errors']}")
        print(f"Unique Error Types: {summary['unique_types']}")
        print()
        
        if summary['by_type']:
            print(f"{'Error Type':<30} {'Count':>8} {'Latest Occurrence'}")
            print("-" * 80)
            for error_type, data in list(summary['by_type'].items())[:10]:
                print(f"{error_type:<30} {data['count']:>8} {data['latest']}")
                print(f"  Message: {data['message'][:70]}")
                print()
        else:
            print("✅ No errors recorded")
        
        print("=" * 80)
    
    def clear_old_errors(self, days=30):
        """Clear errors older than specified days."""
        if not self.error_log.exists():
            return
        
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        # Read all errors
        with open(self.error_log) as f:
            all_errors = [json.loads(line) for line in f]
        
        # Filter recent errors
        recent_errors = [e for e in all_errors if e['timestamp'] >= cutoff]
        
        # Write back
        with open(self.error_log, 'w') as f:
            for error in recent_errors:
                f.write(json.dumps(error) + '\n')
        
        removed = len(all_errors) - len(recent_errors)
        print(f"🧹 Cleaned {removed} old errors (kept last {days} days)")

# Global error tracker
error_tracker = ErrorTracker()

def handle_exception(exc_type, exc_value, exc_traceback):
    """Global exception handler."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    error_tracker.log_error(exc_value, context={'global_handler': True})

# Install global exception handler
sys.excepthook = handle_exception

if __name__ == '__main__':
    # Test error tracking
    try:
        raise ValueError("Test error")
    except Exception as e:
        error_tracker.log_error(e, context={'test': True})
    
    error_tracker.print_report()
