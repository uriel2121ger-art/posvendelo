import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'sat_catalogos.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()

        # ClaveProdServ
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS clave_prod_serv (
            clave TEXT PRIMARY KEY,
            descripcion TEXT,
            iva_trasladado BOOLEAN,
            ieps_trasladado BOOLEAN
        )
        ''')

        # ClaveUnidad
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS clave_unidad (
            clave TEXT PRIMARY KEY,
            nombre TEXT,
            descripcion TEXT
        )
        ''')

        # RegimenFiscal
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS regimen_fiscal (
            clave TEXT PRIMARY KEY,
            descripcion TEXT,
            fisica BOOLEAN,
            moral BOOLEAN
        )
        ''')

        # CodigoPostal (Simplified for validation)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS codigo_postal (
            codigo TEXT PRIMARY KEY,
            estado TEXT,
            municipio TEXT,
            localidad TEXT
        )
        ''')

        # Insert sample data
        cursor.execute("INSERT OR IGNORE INTO clave_prod_serv (clave, descripcion, iva_trasladado, ieps_trasladado) VALUES ('84111506', 'Servicios de facturación', 1, 0)")
        cursor.execute("INSERT OR IGNORE INTO clave_prod_serv (clave, descripcion, iva_trasladado, ieps_trasladado) VALUES ('50202306', 'Refresco', 1, 0)")

        # ClaveUnidad: H87 (Pieza)
        cursor.execute("INSERT OR IGNORE INTO clave_unidad (clave, nombre, descripcion) VALUES ('H87', 'Pieza', 'Pieza')")
        cursor.execute("INSERT OR IGNORE INTO clave_unidad (clave, nombre, descripcion) VALUES ('E48', 'Unidad de servicio', 'Unidad de servicio')")

        # RegimenFiscal
        cursor.execute("INSERT OR IGNORE INTO regimen_fiscal (clave, descripcion, fisica, moral) VALUES ('601', 'General de Ley Personas Morales', 0, 1)")
        cursor.execute("INSERT OR IGNORE INTO regimen_fiscal (clave, descripcion, fisica, moral) VALUES ('616', 'Sin obligaciones fiscales', 1, 0)")
        cursor.execute("INSERT OR IGNORE INTO regimen_fiscal (clave, descripcion, fisica, moral) VALUES ('626', 'Régimen Simplificado de Confianza', 1, 1)")

        # CodigoPostal
        cursor.execute("INSERT OR IGNORE INTO codigo_postal (codigo, estado, municipio, localidad) VALUES ('06000', 'Ciudad de México', 'Cuauhtémoc', 'Ciudad de México')")
        cursor.execute("INSERT OR IGNORE INTO codigo_postal (codigo, estado, municipio, localidad) VALUES ('64000', 'Nuevo León', 'Monterrey', 'Monterrey')")

        conn.commit()
        print(f"Base de datos fiscal inicializada en {DB_PATH}")
    except Exception as e:
        print(f"Error inicializando base de datos fiscal: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    init_db()
