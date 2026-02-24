"""
Hardware Shield - Monitor de Salud del Hardware
Protección contra sobrecalentamiento para Mini-PCs en climas cálidos (Mérida 40°C+)
"""

from typing import Any, Callable, Dict, Optional
import logging
import os
from pathlib import Path
import threading
import time

logger = logging.getLogger(__name__)

class HardwareShield:
    """
    Monitor de salud del hardware con protección contra sobrecalentamiento.
    
    Características:
    - Monitoreo de temperatura de CPU
    - Alertas cuando temperatura supera umbrales
    - Bloqueo automático de operaciones pesadas
    - Notificaciones Push vía PWA
    """
    
    # Umbrales de temperatura (°C)
    TEMP_WARNING = 70    # Advertencia
    TEMP_CRITICAL = 80   # Crítico - reducir carga
    TEMP_EMERGENCY = 90  # Emergencia - bloquear todo
    
    def __init__(self, 
                 on_warning: Optional[Callable] = None,
                 on_critical: Optional[Callable] = None,
                 on_emergency: Optional[Callable] = None):
        """
        Inicializa el Hardware Shield.
        
        Args:
            on_warning: Callback cuando temp > TEMP_WARNING
            on_critical: Callback cuando temp > TEMP_CRITICAL
            on_emergency: Callback cuando temp > TEMP_EMERGENCY
        """
        self.on_warning = on_warning
        self.on_critical = on_critical
        self.on_emergency = on_emergency
        
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._check_interval = 30  # segundos
        
        self.last_temp: float = 0.0
        self.last_status: str = "OK"
        self.heavy_ops_blocked: bool = False

        # Lock for thread-safe access to temp_history
        self._history_lock = threading.Lock()

        # Historial de temperaturas (ultimas 60 lecturas = ~30 min)
        self.temp_history: list = []
        self.max_history = 60
    
    def get_cpu_temperature(self) -> Optional[float]:
        """
        Lee la temperatura del CPU desde sensores del sistema.
        
        Returns:
            Temperatura en °C o None si no se puede leer
        """
        temp_sources = [
            # Linux - thermal zones
            "/sys/class/thermal/thermal_zone0/temp",
            "/sys/class/thermal/thermal_zone1/temp",
            "/sys/class/thermal/thermal_zone2/temp",
            # Raspberry Pi
            "/sys/class/thermal/thermal_zone0/temp",
            # AMD/Intel específicos
            "/sys/devices/platform/coretemp.0/hwmon/hwmon*/temp1_input",
        ]
        
        for source in temp_sources:
            try:
                # Manejar wildcards
                if '*' in source:
                    import glob
                    matches = glob.glob(source)
                    if matches:
                        source = matches[0]
                    else:
                        continue
                
                if os.path.exists(source):
                    with open(source, 'r') as f:
                        temp_raw = f.read().strip()
                        # Convertir de milicelsius a celsius
                        temp_c = float(temp_raw) / 1000.0
                        return temp_c
            except Exception as e:
                logger.debug(f"Error leyendo {source}: {e}")
                continue
        
        # Fallback: usar lm-sensors si está disponible
        try:
            import subprocess
            result = subprocess.run(
                ['sensors', '-u'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'temp1_input' in line or 'Core 0' in line:
                        parts = line.split(':')
                        if len(parts) > 1:
                            temp_parts = parts[1].strip().split()
                            if temp_parts and len(temp_parts) > 0:
                                try:
                                    temp = float(temp_parts[0])
                                    return temp
                                except (ValueError, TypeError):
                                    pass
        except Exception as e:
            logger.debug("get_cpu_temperature: %s", e)
        
        return None
    
    def get_system_stats(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas completas del sistema.
        
        Returns:
            Dict con temperatura, uso de CPU, RAM, disco
        """
        stats = {
            "temperature_c": self.get_cpu_temperature(),
            "status": "UNKNOWN",
            "heavy_ops_blocked": self.heavy_ops_blocked,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Uso de CPU
        try:
            with open('/proc/stat', 'r') as f:
                cpu_line = f.readline()
                parts = cpu_line.split()
                idle = float(parts[4])
                total = sum(float(p) for p in parts[1:])
                stats["cpu_percent"] = round(100 * (1 - idle / total), 1)
        except Exception as e:
            logger.debug("CPU stats: %s", e)
            stats["cpu_percent"] = None
        
        # Uso de memoria
        try:
            with open('/proc/meminfo', 'r') as f:
                meminfo = {}
                for line in f:
                    parts = line.split(':')
                    if len(parts) == 2:
                        key = parts[0].strip()
                        val_parts = parts[1].strip().split()
                        if val_parts and len(val_parts) > 0:
                            try:
                                val = int(val_parts[0])
                                meminfo[key] = val
                            except (ValueError, TypeError):
                                pass
                
                total = meminfo.get('MemTotal', 1)
                available = meminfo.get('MemAvailable', 0)
                used_percent = 100 * (1 - available / total)
                stats["ram_percent"] = round(used_percent, 1)
                stats["ram_total_gb"] = round(total / 1024 / 1024, 1)
        except Exception as e:
            logger.debug("RAM stats: %s", e)
            stats["ram_percent"] = None
        
        # Uso de disco
        try:
            import shutil
            usage = shutil.disk_usage('/')
            stats["disk_percent"] = round(100 * usage.used / usage.total, 1)
            stats["disk_free_gb"] = round(usage.free / 1024 / 1024 / 1024, 1)
        except Exception as e:
            logger.debug("Disk stats: %s", e)
            stats["disk_percent"] = None
        
        # Determinar estado
        temp = stats.get("temperature_c")
        if temp is not None:
            if temp >= self.TEMP_EMERGENCY:
                stats["status"] = "🔴 EMERGENCIA"
            elif temp >= self.TEMP_CRITICAL:
                stats["status"] = "🟠 CRÍTICO"
            elif temp >= self.TEMP_WARNING:
                stats["status"] = "🟡 ADVERTENCIA"
            else:
                stats["status"] = "🟢 OK"
        
        return stats
    
    def check_and_alert(self) -> str:
        """
        Verifica temperatura y dispara alertas si es necesario.
        
        Returns:
            Estado actual: "OK", "WARNING", "CRITICAL", "EMERGENCY"
        """
        temp = self.get_cpu_temperature()
        
        if temp is None:
            logger.warning("⚠️ No se pudo leer temperatura del CPU")
            return "UNKNOWN"
        
        self.last_temp = temp

        # Guardar en historial (thread-safe)
        with self._history_lock:
            self.temp_history.append(temp)
            if len(self.temp_history) > self.max_history:
                self.temp_history.pop(0)
        
        # Evaluar umbrales
        if temp >= self.TEMP_EMERGENCY:
            self.last_status = "EMERGENCY"
            self.heavy_ops_blocked = True
            logger.critical(f"🔴 EMERGENCIA TÉRMICA: {temp}°C - Bloqueando operaciones pesadas")
            if self.on_emergency:
                self.on_emergency(temp)
        
        elif temp >= self.TEMP_CRITICAL:
            self.last_status = "CRITICAL"
            self.heavy_ops_blocked = True
            logger.warning(f"🟠 TEMPERATURA CRÍTICA: {temp}°C - Reduciendo carga")
            if self.on_critical:
                self.on_critical(temp)
        
        elif temp >= self.TEMP_WARNING:
            self.last_status = "WARNING"
            self.heavy_ops_blocked = False
            logger.warning(f"🟡 Advertencia de temperatura: {temp}°C")
            if self.on_warning:
                self.on_warning(temp)
        
        else:
            self.last_status = "OK"
            self.heavy_ops_blocked = False
            logger.debug(f"🟢 Temperatura normal: {temp}°C")
        
        return self.last_status
    
    def start_monitoring(self, interval_seconds: int = 30):
        """
        Inicia monitoreo en segundo plano.
        
        Args:
            interval_seconds: Intervalo entre lecturas
        """
        if self._monitoring:
            logger.warning("Monitoreo ya está activo")
            return
        
        self._check_interval = interval_seconds
        self._monitoring = True
        
        def monitor_loop():
            logger.info(f"🌡️ Hardware Shield iniciado (intervalo: {interval_seconds}s)")
            while self._monitoring:
                try:
                    self.check_and_alert()
                except Exception as e:
                    logger.error(f"Error en monitoreo: {e}")
                time.sleep(self._check_interval)
        
        self._monitor_thread = threading.Thread(
            target=monitor_loop,
            daemon=True,
            name="HardwareShield"
        )
        self._monitor_thread.start()
    
    def stop_monitoring(self):
        """Detiene el monitoreo en segundo plano."""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        logger.info("🛑 Hardware Shield detenido")
    
    def can_run_heavy_operation(self) -> bool:
        """
        Verifica si es seguro ejecutar operaciones pesadas (IA, reportes grandes).
        
        Returns:
            True si es seguro, False si hay riesgo térmico
        """
        if self.heavy_ops_blocked:
            logger.warning("⛔ Operación pesada bloqueada por riesgo térmico")
            return False
        
        # Verificación adicional en tiempo real
        temp = self.get_cpu_temperature()
        if temp and temp >= self.TEMP_CRITICAL:
            logger.warning(f"⛔ Temperatura actual {temp}°C - Operación bloqueada")
            return False
        
        return True
    
    def get_temperature_trend(self) -> str:
        """
        Analiza la tendencia de temperatura. Thread-safe.

        Returns:
            "RISING", "FALLING", "STABLE", "UNKNOWN"
        """
        with self._history_lock:
            if len(self.temp_history) < 5:
                return "UNKNOWN"

            recent = list(self.temp_history[-5:])
            if len(self.temp_history) >= 10:
                older = list(self.temp_history[-10:-5])
            else:
                older = list(self.temp_history[:5])

        avg_recent = sum(recent) / len(recent)
        avg_older = sum(older) / len(older)

        diff = avg_recent - avg_older

        if diff > 2:
            return "SUBIENDO"
        elif diff < -2:
            return "BAJANDO"
        else:
            return "ESTABLE"
    
    def get_thermal_status(self) -> Dict[str, Any]:
        """
        Retorna estado térmico simplificado.
        
        Returns:
            Dict con temperatura, estado y si operaciones pesadas están bloqueadas
        """
        temp = self.get_cpu_temperature()
        
        if temp is None:
            status = "UNKNOWN"
            icon = "❓"
        elif temp >= self.TEMP_EMERGENCY:
            status = "EMERGENCY"
            icon = "🔴"
        elif temp >= self.TEMP_CRITICAL:
            status = "CRITICAL"
            icon = "🟠"
        elif temp >= self.TEMP_WARNING:
            status = "WARNING"
            icon = "🟡"
        else:
            status = "OK"
            icon = "🟢"
        
        # Get trend (thread-safe check for empty history)
        with self._history_lock:
            has_history = len(self.temp_history) > 0
        trend = self.get_temperature_trend() if has_history else 'UNKNOWN'

        return {
            'temperature': temp,
            'status': status,
            'icon': icon,
            'heavy_ops_blocked': self.heavy_ops_blocked,
            'trend': trend,
            'thresholds': {
                'warning': self.TEMP_WARNING,
                'critical': self.TEMP_CRITICAL,
                'emergency': self.TEMP_EMERGENCY
            }
        }

# Singleton global (thread-safe)
_shield_instance: Optional[HardwareShield] = None
_shield_lock = threading.Lock()


def get_hardware_shield() -> HardwareShield:
    """Obtiene la instancia singleton del Hardware Shield. Thread-safe."""
    global _shield_instance
    if _shield_instance is None:
        with _shield_lock:
            # Double-check after acquiring lock
            if _shield_instance is None:
                _shield_instance = HardwareShield()
    return _shield_instance

def init_hardware_shield(
    on_warning: Optional[Callable] = None,
    on_critical: Optional[Callable] = None,
    on_emergency: Optional[Callable] = None,
    start_monitoring: bool = True
) -> HardwareShield:
    """
    Inicializa el Hardware Shield con callbacks personalizados. Thread-safe.

    Args:
        on_warning: Callback para advertencias (>70°C)
        on_critical: Callback para crítico (>80°C)
        on_emergency: Callback para emergencia (>90°C)
        start_monitoring: Si iniciar monitoreo automático

    Returns:
        Instancia del HardwareShield
    """
    global _shield_instance
    with _shield_lock:
        _shield_instance = HardwareShield(
            on_warning=on_warning,
            on_critical=on_critical,
            on_emergency=on_emergency
        )

        if start_monitoring:
            _shield_instance.start_monitoring()

    return _shield_instance
