#!/usr/bin/env python3
"""
TITAN POS - Herramienta de Manipulación Manual de Base de Datos
Permite insertar, actualizar, consultar y exportar datos de forma segura
"""

import sys
import os
import sqlite3
import json
import csv
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

# Agregar el directorio raíz al path
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Colores para terminal
GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'  # No Color

def log_success(msg):
    print(f"{GREEN}[✓]{NC} {msg}")

def log_error(msg):
    print(f"{RED}[✗]{NC} {msg}")

def log_warning(msg):
    print(f"{YELLOW}[!]{NC} {msg}")

def log_info(msg):
    print(f"{BLUE}[i]{NC} {msg}")

class DatabaseManualTool:
    """Herramienta interactiva para manipulación manual de la base de datos."""
    
    def __init__(self, db_path: Optional[str] = None):
        """Inicializar herramienta."""
        if db_path is None:
            # Buscar base de datos en ubicaciones comunes
            possible_paths = [
                PROJECT_ROOT / "data" / "databases" / "pos.db",
                PROJECT_ROOT / "data" / "pos.db",
                Path.home() / "titan-pos" / "data" / "databases" / "pos.db",
            ]
            
            for path in possible_paths:
                if path.exists():
                    db_path = str(path)
                    break
        
        if not db_path or not Path(db_path).exists():
            log_error(f"Base de datos no encontrada. Buscada en: {[str(p) for p in possible_paths]}")
            sys.exit(1)
        
        self.db_path = db_path
        self.conn = None
        self.log_file = PROJECT_ROOT / "logs" / "db_manual_tool.log"
        self.log_file.parent.mkdir(exist_ok=True)
        
        log_info(f"Conectando a base de datos: {db_path}")
        self._connect()
    
    def _connect(self):
        """Conectar a la base de datos."""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            log_success("Conexión establecida")
        except sqlite3.Error as e:
            log_error(f"Error conectando a la base de datos: {e}")
            sys.exit(1)
    
    def _log_operation(self, operation: str, details: str):
        """Registrar operación en log."""
        timestamp = datetime.now().isoformat()
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(f"{timestamp} | {operation} | {details}\n")
    
    def _get_tables(self) -> List[str]:
        """Obtener lista de tablas."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        return [row[0] for row in cursor.fetchall()]
    
    def _get_table_info(self, table_name: str) -> List[Dict[str, Any]]:
        """Obtener información de columnas de una tabla."""
        cursor = self.conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = []
        for row in cursor.fetchall():
            columns.append({
                'name': row[1],
                'type': row[2],
                'notnull': row[3],
                'default': row[4],
                'pk': row[5]
            })
        return columns
    
    def _validate_table_name(self, table_name: str) -> bool:
        """Validar que el nombre de tabla es seguro."""
        if not table_name.isalnum() and '_' not in table_name:
            return False
        return table_name in self._get_tables()
    
    def insert_data(self):
        """Insertar datos manualmente."""
        print("\n" + "="*70)
        print("INSERTAR DATOS")
        print("="*70)
        
        tables = self._get_tables()
        print("\nTablas disponibles:")
        for i, table in enumerate(tables, 1):
            print(f"  {i}) {table}")
        
        try:
            choice = int(input("\nSelecciona tabla (número): "))
            if choice < 1 or choice > len(tables):
                log_error("Selección inválida")
                return
            table_name = tables[choice - 1]
        except (ValueError, KeyboardInterrupt):
            return
        
        # Obtener información de columnas
        columns = self._get_table_info(table_name)
        print(f"\nColumnas de {table_name}:")
        for col in columns:
            required = "REQUERIDO" if col['notnull'] and not col['pk'] else "opcional"
            pk = " (PRIMARY KEY)" if col['pk'] else ""
            print(f"  - {col['name']}: {col['type']} {required}{pk}")
        
        # Recopilar valores
        values = {}
        for col in columns:
            if col['pk'] and 'AUTOINCREMENT' in str(col):
                continue  # Skip auto-increment columns
            
            while True:
                value = input(f"\n{col['name']} ({col['type']}): ").strip()
                
                if not value:
                    if col['notnull'] and not col['pk']:
                        log_error("Este campo es requerido")
                        continue
                    break
                
                # Validar tipo básico
                if col['type'].upper() in ('INTEGER', 'INT'):
                    try:
                        values[col['name']] = int(value)
                        break
                    except ValueError:
                        log_error("Debe ser un número entero")
                        continue
                elif col['type'].upper() in ('REAL', 'FLOAT', 'NUMERIC'):
                    try:
                        values[col['name']] = float(value)
                        break
                    except ValueError:
                        log_error("Debe ser un número")
                        continue
                else:
                    values[col['name']] = value
                    break
        
        # Confirmar inserción
        print(f"\nDatos a insertar en {table_name}:")
        for key, val in values.items():
            print(f"  {key}: {val}")
        
        confirm = input("\n¿Confirmar inserción? (s/n): ").strip().lower()
        if confirm != 's':
            log_info("Inserción cancelada")
            return
        
        # Insertar
        try:
            columns_str = ', '.join(values.keys())
            placeholders = ', '.join(['?' for _ in values])
            query = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"
            
            cursor = self.conn.cursor()
            cursor.execute(query, tuple(values.values()))
            self.conn.commit()
            
            log_success(f"Datos insertados en {table_name} (ID: {cursor.lastrowid})")
            self._log_operation("INSERT", f"{table_name}: {values}")
        except sqlite3.Error as e:
            log_error(f"Error insertando datos: {e}")
            self.conn.rollback()
    
    def update_data(self):
        """Actualizar datos."""
        print("\n" + "="*70)
        print("ACTUALIZAR DATOS")
        print("="*70)
        
        tables = self._get_tables()
        print("\nTablas disponibles:")
        for i, table in enumerate(tables, 1):
            print(f"  {i}) {table}")
        
        try:
            choice = int(input("\nSelecciona tabla (número): "))
            if choice < 1 or choice > len(tables):
                log_error("Selección inválida")
                return
            table_name = tables[choice - 1]
        except (ValueError, KeyboardInterrupt):
            return
        
        # Buscar registro
        search_field = input("\nCampo para buscar (ID, SKU, nombre, etc.): ").strip()
        # Validar que el campo existe en la tabla
        valid_columns = [col['name'] for col in self._get_table_info(table_name)]
        if search_field not in valid_columns:
            log_warning(f"Campo '{search_field}' no existe. Columnas válidas: {', '.join(valid_columns)}")
            return
        search_value = input(f"Valor a buscar en '{search_field}': ").strip()

        # Buscar
        try:
            query = f"SELECT * FROM {table_name} WHERE {search_field} = ? LIMIT 10"
            cursor = self.conn.cursor()
            cursor.execute(query, (search_value,))
            results = cursor.fetchall()
            
            if not results:
                log_warning("No se encontraron registros")
                return
            
            print(f"\nRegistros encontrados ({len(results)}):")
            for i, row in enumerate(results, 1):
                print(f"\n  {i}) {dict(row)}")
            
            if len(results) > 1:
                record_num = int(input("\nSelecciona registro a actualizar (número): "))
                if record_num < 1 or record_num > len(results):
                    log_error("Selección inválida")
                    return
                record = results[record_num - 1]
            else:
                record = results[0]
            
            # Obtener columnas editables
            columns = self._get_table_info(table_name)
            editable_cols = [col for col in columns if not col['pk']]
            
            print("\nColumnas editables:")
            for i, col in enumerate(editable_cols, 1):
                current_value = record[col['name']]
                print(f"  {i}) {col['name']} ({col['type']}): {current_value}")
            
            # Seleccionar campos a actualizar
            fields_to_update = {}
            while True:
                try:
                    col_choice = input("\nCampo a actualizar (número, o 'fin' para terminar): ").strip()
                    if col_choice.lower() == 'fin':
                        break
                    
                    col_idx = int(col_choice) - 1
                    if col_idx < 0 or col_idx >= len(editable_cols):
                        log_error("Selección inválida")
                        continue
                    
                    col = editable_cols[col_idx]
                    new_value = input(f"Nuevo valor para {col['name']}: ").strip()
                    
                    # Validar tipo
                    if col['type'].upper() in ('INTEGER', 'INT'):
                        new_value = int(new_value)
                    elif col['type'].upper() in ('REAL', 'FLOAT', 'NUMERIC'):
                        new_value = float(new_value)
                    elif not new_value:
                        new_value = None
                    
                    fields_to_update[col['name']] = new_value
                    print(f"  ✓ {col['name']} = {new_value}")
                except (ValueError, KeyboardInterrupt):
                    break
            
            if not fields_to_update:
                log_info("No hay campos para actualizar")
                return
            
            # Confirmar
            print(f"\nActualizar registro en {table_name}:")
            for key, val in fields_to_update.items():
                print(f"  {key}: {val}")
            
            confirm = input("\n¿Confirmar actualización? (s/n): ").strip().lower()
            if confirm != 's':
                log_info("Actualización cancelada")
                return
            
            # Actualizar
            set_clause = ', '.join([f"{k} = ?" for k in fields_to_update.keys()])
            pk_col = next((col['name'] for col in columns if col['pk']), None)
            
            if not pk_col:
                log_error("No se encontró columna de clave primaria")
                return
            
            update_query = f"UPDATE {table_name} SET {set_clause} WHERE {pk_col} = ?"
            cursor.execute(update_query, tuple(fields_to_update.values()) + (record[pk_col],))
            self.conn.commit()
            
            log_success(f"Registro actualizado en {table_name}")
            self._log_operation("UPDATE", f"{table_name}: {fields_to_update}")
            
        except sqlite3.Error as e:
            log_error(f"Error actualizando datos: {e}")
            self.conn.rollback()
        except (ValueError, KeyboardInterrupt):
            return
    
    def execute_sql(self):
        """Ejecutar SQL personalizado."""
        print("\n" + "="*70)
        print("EJECUTAR SQL PERSONALIZADO")
        print("="*70)
        print("\n⚠️  MODO SEGURO: Solo se permiten consultas SELECT por defecto")
        print("   Para INSERT/UPDATE/DELETE, activa el modo avanzado")
        
        mode = input("\n¿Modo avanzado? (permite INSERT/UPDATE/DELETE) (s/n): ").strip().lower()
        advanced = mode == 's'
        
        if advanced:
            log_warning("MODO AVANZADO ACTIVADO - Ten cuidado con las operaciones destructivas")
        
        while True:
            sql = input("\nSQL (o 'salir' para terminar): ").strip()
            
            if sql.lower() == 'salir':
                break
            
            if not sql:
                continue
            
            # Validar en modo seguro
            if not advanced:
                sql_upper = sql.upper().strip()
                if any(sql_upper.startswith(cmd) for cmd in ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER', 'CREATE']):
                    log_error("Operaciones destructivas no permitidas en modo seguro")
                    log_info("Activa el modo avanzado para permitir estas operaciones")
                    continue
            
            try:
                cursor = self.conn.cursor()
                cursor.execute(sql)
                
                if sql.upper().strip().startswith('SELECT'):
                    results = cursor.fetchall()
                    if results:
                        print(f"\nResultados ({len(results)} filas):")
                        for row in results[:20]:  # Limitar a 20 filas
                            print(f"  {dict(row)}")
                        if len(results) > 20:
                            print(f"  ... y {len(results) - 20} filas más")
                    else:
                        print("\nNo se encontraron resultados")
                else:
                    self.conn.commit()
                    log_success(f"Consulta ejecutada. Filas afectadas: {cursor.rowcount}")
                    self._log_operation("SQL", sql)
                    
            except sqlite3.Error as e:
                log_error(f"Error ejecutando SQL: {e}")
                self.conn.rollback()
    
    def export_table(self):
        """Exportar tabla a CSV o JSON."""
        print("\n" + "="*70)
        print("EXPORTAR TABLA")
        print("="*70)
        
        tables = self._get_tables()
        print("\nTablas disponibles:")
        for i, table in enumerate(tables, 1):
            print(f"  {i}) {table}")
        
        try:
            choice = int(input("\nSelecciona tabla (número): "))
            if choice < 1 or choice > len(tables):
                log_error("Selección inválida")
                return
            table_name = tables[choice - 1]
        except (ValueError, KeyboardInterrupt):
            return
        
        format_choice = input("\nFormato (csv/json): ").strip().lower()
        if format_choice not in ['csv', 'json']:
            log_error("Formato inválido")
            return
        
        output_file = input(f"Archivo de salida (o Enter para {table_name}.{format_choice}): ").strip()
        if not output_file:
            output_file = f"{table_name}.{format_choice}"
        
        try:
            cursor = self.conn.cursor()
            cursor.execute(f"SELECT * FROM {table_name}")
            results = cursor.fetchall()
            
            if format_choice == 'csv':
                with open(output_file, 'w', newline='', encoding='utf-8') as f:
                    if results:
                        writer = csv.DictWriter(f, fieldnames=results[0].keys())
                        writer.writeheader()
                        writer.writerows([dict(row) for row in results])
            else:  # json
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump([dict(row) for row in results], f, indent=2, default=str)
            
            log_success(f"Tabla {table_name} exportada a {output_file} ({len(results)} filas)")
            self._log_operation("EXPORT", f"{table_name} -> {output_file}")
            
        except Exception as e:
            log_error(f"Error exportando: {e}")
    
    def verify_integrity(self):
        """Verificar integridad de la base de datos."""
        print("\n" + "="*70)
        print("VERIFICAR INTEGRIDAD")
        print("="*70)
        
        try:
            # Verificar integridad general
            cursor = self.conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            result = cursor.fetchone()[0]
            
            if result == 'ok':
                log_success("Integridad de la base de datos: OK")
            else:
                log_error(f"Problemas de integridad: {result}")
            
            # Verificar foreign keys
            cursor.execute("PRAGMA foreign_key_check;")
            fk_errors = cursor.fetchall()
            if fk_errors:
                log_warning(f"Se encontraron {len(fk_errors)} errores de foreign key")
                for error in fk_errors[:5]:
                    print(f"  {error}")
            else:
                log_success("Foreign keys: OK")
            
            # Verificar índices
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'")
            indexes = cursor.fetchall()
            log_info(f"Índices encontrados: {len(indexes)}")
            
        except sqlite3.Error as e:
            log_error(f"Error verificando integridad: {e}")
    
    def menu(self):
        """Menú principal."""
        while True:
            print("\n" + "="*70)
            print("HERRAMIENTA DE MANIPULACIÓN MANUAL DE BASE DE DATOS")
            print("="*70)
            print("\nOpciones:")
            print("  1) Insertar datos")
            print("  2) Actualizar datos")
            print("  3) Ejecutar SQL personalizado")
            print("  4) Exportar tabla a CSV/JSON")
            print("  5) Verificar integridad")
            print("  6) Salir")
            
            try:
                choice = input("\nSelecciona opción: ").strip()
                
                if choice == '1':
                    self.insert_data()
                elif choice == '2':
                    self.update_data()
                elif choice == '3':
                    self.execute_sql()
                elif choice == '4':
                    self.export_table()
                elif choice == '5':
                    self.verify_integrity()
                elif choice == '6':
                    log_info("Saliendo...")
                    break
                else:
                    log_error("Opción inválida")
            except KeyboardInterrupt:
                print("\n")
                log_info("Saliendo...")
                break
            except Exception as e:
                log_error(f"Error: {e}")
        
        if self.conn:
            self.conn.close()

def main():
    """Función principal."""
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║   HERRAMIENTA DE MANIPULACIÓN MANUAL DE BASE DE DATOS       ║")
    print("║                    TITAN POS                                 ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    
    # Permitir especificar ruta de DB como argumento
    db_path = sys.argv[1] if len(sys.argv) > 1 else None
    
    tool = DatabaseManualTool(db_path)
    tool.menu()

if __name__ == "__main__":
    main()
