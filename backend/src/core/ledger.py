import hashlib
import logging
from typing import Optional, Union
from decimal import Decimal


logger = logging.getLogger(__name__)


class BlockchainLedger:
    """
    Blockchain ledger para verificación de integridad de ventas.

    Compatible con SQLite y PostgreSQL.
    """
    def __init__(self, db_manager):
        """
        Inicializa el ledger.

        Args:
            db_manager: Instancia de DatabaseManager

        Raises:
            ValueError: Si db_manager es None
        """
        if db_manager is None:
            raise ValueError("db_manager es requerido")
        self.db = db_manager

    def _calculate_hash(self, prev_hash: str, data: str) -> str:
        """Genera SHA-256 del bloque actual + anterior."""
        payload = f"{prev_hash}|{data}".encode('utf-8')
        return hashlib.sha256(payload).hexdigest()

    def register_transaction(
        self,
        sale_uuid: str,
        total: Union[Decimal, float, str],
        timestamp: str
    ) -> str:
        """
        Registra una venta en la cadena de bloques.

        Args:
            sale_uuid: UUID unico de la venta
            total: Total de la venta (Decimal, float o str)
            timestamp: Timestamp de la venta

        Returns:
            Hash calculado para la transaccion

        Raises:
            ValueError: Si los parametros son invalidos
        """
        # Validacion de parametros
        if not sale_uuid or not isinstance(sale_uuid, str):
            raise ValueError("sale_uuid es requerido y debe ser string")
        if not timestamp or not isinstance(timestamp, str):
            raise ValueError("timestamp es requerido y debe ser string")
        if total is None:
            raise ValueError("total es requerido")

        # Convertir total a Decimal para precision
        import decimal as decimal_module
        try:
            total_decimal = Decimal(str(total))
        except (decimal_module.InvalidOperation, ValueError, TypeError) as e:
            raise ValueError(f"total invalido: {e}")

        # 1. Obtener el hash de la última venta
        # Usar id o created_at en lugar de rowid (SQLite específico)
        result = self.db.execute_query(
            "SELECT hash FROM sales ORDER BY id DESC LIMIT 1"
        )
        
        prev_hash = "GENESIS_BLOCK_0000000000000000"
        if result:
            row = result[0]
            if isinstance(row, dict):
                prev_hash = row.get('hash', prev_hash) or prev_hash
            else:
                prev_hash = row[0] if row[0] else prev_hash
        
        # 2. Calcular nuevo hash
        # Data incluye UUID, Total y Timestamp para hacerla inmutable
        # Usar total_decimal para consistencia
        data_string = f"{sale_uuid}:{total_decimal}:{timestamp}"
        new_hash = self._calculate_hash(prev_hash, data_string)
        
        # 3. Actualizar registro (se asume que el INSERT ya ocurrió o se hará en transacción)
        self.db.execute_write(
            "UPDATE sales SET prev_hash=%s, hash=%s, synced=0, updated_at=CURRENT_TIMESTAMP WHERE uuid=%s",
            (prev_hash, new_hash, sale_uuid)
        )
        
        return new_hash

    def verify_integrity(self) -> bool:
        """
        Recorre toda la cadena para verificar que nadie manipuló la DB.
        Retorna True si la cadena es válida.
        """
        # Usar id o created_at en lugar de rowid (SQLite específico)
        rows = self.db.execute_query(
            "SELECT uuid, total, timestamp, prev_hash, hash FROM sales ORDER BY id ASC"
        )
        
        last_hash = "GENESIS_BLOCK_0000000000000000"
        
        for row in rows:
            if isinstance(row, dict):
                uuid = row.get('uuid')
                total = row.get('total')
                ts = row.get('timestamp')
                stored_prev = row.get('prev_hash')
                stored_hash = row.get('hash')
            else:
                uuid, total, ts, stored_prev, stored_hash = row
            
            # 1. Verificar enlace con el anterior
            if stored_prev != last_hash:
                logging.critical(f"🚨 BLOCKCHAIN BROKEN at UUID {uuid}. Prev Hash Mismatch!")
                return False
            
            # 2. Recalcular hash actual
            data_string = f"{uuid}:{total}:{ts}"
            calculated_hash = self._calculate_hash(last_hash, data_string)
            
            if calculated_hash != stored_hash:
                logging.critical(f"🚨 DATA TAMPERING at UUID {uuid}. Hash Mismatch!")
                return False
                
            last_hash = stored_hash
        
        return True
