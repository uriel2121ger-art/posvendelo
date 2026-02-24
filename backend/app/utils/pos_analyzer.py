"""
TITAN POS - Sistema de Análisis y Logging Avanzado
Este módulo registra todas las acciones, errores y comportamientos del sistema
"""
from datetime import datetime
import json
import logging
from pathlib import Path
import sys
import traceback


class POSAnalyzer:
    def __init__(self, log_dir="logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_file = self.log_dir / f"session_{timestamp}.log"
        self.error_file = self.log_dir / f"errors_{timestamp}.log"
        self.actions_file = self.log_dir / f"actions_{timestamp}.jsonl"
        
        # Setup loggers
        self.setup_loggers()
        
        # Action counter
        self.action_count = 0
        
    def setup_loggers(self):
        """Configura múltiples loggers para diferentes propósitos"""
        
        # Logger general
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.session_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        # Logger de errores
        self.error_logger = logging.getLogger('ERRORS')
        error_handler = logging.FileHandler(self.error_file)
        error_handler.setLevel(logging.ERROR)
        error_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s\n%(pathname)s:%(lineno)d\n'
        )
        error_handler.setFormatter(error_formatter)
        self.error_logger.addHandler(error_handler)
        
        # Logger de acciones
        self.action_logger = logging.getLogger('ACTIONS')
        
    def log_action(self, action_type, details, user=None):
        """Registra una acción del usuario o sistema"""
        self.action_count += 1
        
        action_record = {
            "id": self.action_count,
            "timestamp": datetime.now().isoformat(),
            "type": action_type,
            "details": details,
            "user": user
        }
        
        with open(self.actions_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(action_record, ensure_ascii=False) + '\n')
            
        logging.info(f"ACTION: {action_type} - {details}")
        
    def log_error(self, error, context=""):
        """Registra un error con contexto completo"""
        error_info = {
            "timestamp": datetime.now().isoformat(),
            "error": str(error),
            "type": type(error).__name__,
            "context": context,
            "traceback": traceback.format_exc()
        }
        
        self.error_logger.error(json.dumps(error_info, indent=2))
        logging.error(f"ERROR in {context}: {error}")
        
    def log_system_event(self, event_type, message):
        """Registra eventos del sistema"""
        logging.info(f"SYSTEM EVENT: {event_type} - {message}")
        
    def generate_report(self):
        """Genera un reporte de la sesión"""
        report_file = self.log_dir / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        with open(report_file, 'w') as f:
            f.write("="*80 + "\n")
            f.write("TITAN POS - REPORTE DE ANÁLISIS DE SESIÓN\n")
            f.write("="*80 + "\n\n")
            f.write(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total de acciones registradas: {self.action_count}\n\n")
            
            # Resumen de errores
            if self.error_file.exists():
                f.write("-"*80 + "\n")
                f.write("ERRORES DETECTADOS:\n")
                f.write("-"*80 + "\n")
                with open(self.error_file) as ef:
                    f.write(ef.read())
                    
        return report_file

# Instancia global
analyzer = None

def initialize_analyzer():
    global analyzer
    analyzer = POSAnalyzer()
    return analyzer

def get_analyzer():
    global analyzer
    if analyzer is None:
        analyzer = initialize_analyzer()
    return analyzer
