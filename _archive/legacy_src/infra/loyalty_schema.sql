-- ============================================================================
-- PROTOCOLO MIDAS - LOYALTY & CASHBACK SYSTEM
-- Sistema de Monedero Electrónico con Prevención de Fraude
-- $1 Punto = $1 Peso (configurable)
-- ============================================================================

-- 1. CUENTAS DE LEALTAD (El Balance)
CREATE TABLE IF NOT EXISTS loyalty_accounts (
    id BIGSERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL UNIQUE,
    saldo_actual DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    saldo_pendiente DECIMAL(10,2) DEFAULT 0.00, -- Puntos en verificación
    nivel_lealtad TEXT DEFAULT 'BRONCE', -- BRONCE, PLATA, ORO, PLATINO
    fecha_ultima_actividad TEXT,
    fecha_creacion TIMESTAMP DEFAULT NOW(),
    status TEXT DEFAULT 'ACTIVE', -- ACTIVE, SUSPENDED, BLOCKED
    flags_fraude INTEGER DEFAULT 0, -- Contador de alertas
    ultima_alerta TEXT,
    
    -- Constraint: El saldo NUNCA puede ser negativo
    CHECK (saldo_actual >= 0),
    
    FOREIGN KEY(customer_id) REFERENCES customers(id) ON DELETE CASCADE
);

-- 2. LOYALTY LEDGER (Kardex Inmutable - The Source of Truth)
CREATE TABLE IF NOT EXISTS loyalty_ledger (
    id BIGSERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL,
    customer_id INTEGER NOT NULL,
    
    -- Datos de Transacción
    fecha_hora TIMESTAMP NOT NULL DEFAULT NOW(),
    tipo TEXT NOT NULL, -- EARN, REDEEM, EXPIRE, ADJUST, REFUND, BONUS
    monto DECIMAL(10,2) NOT NULL,
    saldo_anterior DECIMAL(10,2) NOT NULL,
    saldo_nuevo DECIMAL(10,2) NOT NULL,
    
    -- Referencias
    ticket_referencia_id INTEGER, -- FK a sales.id
    turn_id INTEGER,
    user_id INTEGER, -- Quien procesó
    
    -- Metadata
    descripcion TEXT,
    regla_aplicada TEXT, -- Nombre de la regla que generó estos puntos
    porcentaje_cashback DECIMAL(5,2), -- % aplicado
    
    -- Seguridad Anti-Fraude
    hash_seguridad TEXT, -- SHA256 de la transacción
    ip_address TEXT,
    device_id TEXT,
    
    -- Auditoría
    created_at TIMESTAMP DEFAULT NOW(),
    
    FOREIGN KEY(account_id) REFERENCES loyalty_accounts(id),
    FOREIGN KEY(customer_id) REFERENCES customers(id)
    -- NOTA: ticket_referencia_id y turn_id son campos de referencia opcionales
    -- No usamos FK para permitir que el schema funcione independientemente
);

-- 3. MOTOR DE REGLAS (Configuración Dinámica de Cashback)
CREATE TABLE IF NOT EXISTS loyalty_rules (
    id BIGSERIAL PRIMARY KEY,
    regla_id TEXT UNIQUE NOT NULL, -- Nombre único: "PROMO_PISOS", "BASE_DEFAULT"
    nombre_display TEXT NOT NULL, -- "10% en Pisos los Sábados"
    descripcion TEXT,
    
    -- Condiciones (JSON o campos separados)
    condicion_tipo TEXT DEFAULT 'GLOBAL', -- GLOBAL, CATEGORIA, PRODUCTO, DIA_SEMANA
    condicion_valor TEXT, -- categoria_id, product_id, día de la semana
    
    -- Cashback
    multiplicador DECIMAL(5,4) NOT NULL, -- 0.05 = 5%, 0.10 = 10%
    monto_minimo DECIMAL(10,2) DEFAULT 0.00, -- Compra mínima para activar
    monto_maximo_puntos DECIMAL(10,2), -- Límite de puntos por transacción
    
    -- Vigencia
    vigencia_inicio TEXT,
    vigencia_fin TEXT,
    activo INTEGER DEFAULT 1,
    
    -- Prioridad (reglas con mayor prioridad se aplican primero)
    prioridad INTEGER DEFAULT 0,
    
    -- Restricciones
    aplica_lunes INTEGER DEFAULT 1,
    aplica_martes INTEGER DEFAULT 1,
    aplica_miercoles INTEGER DEFAULT 1,
    aplica_jueves INTEGER DEFAULT 1,
    aplica_viernes INTEGER DEFAULT 1,
    aplica_sabado INTEGER DEFAULT 1,
    aplica_domingo INTEGER DEFAULT 1,
    
    -- Niveles de lealtad aplicables
    aplica_niveles TEXT DEFAULT 'BRONCE,PLATA,ORO,PLATINO',
    
    -- Auditoría
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by INTEGER
);

-- 4. REGISTRO DE FRAUDE (The Shield)
CREATE TABLE IF NOT EXISTS loyalty_fraud_log (
    id BIGSERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL,
    customer_id INTEGER NOT NULL,
    
    tipo_alerta TEXT NOT NULL, -- VELOCITY, ANOMALY, MANUAL
    descripcion TEXT,
    severidad TEXT DEFAULT 'LOW', -- LOW, MEDIUM, HIGH, CRITICAL
    
    -- Datos del Incidente
    fecha_hora TIMESTAMP DEFAULT NOW(),
    transacciones_recientes INTEGER,
    monto_involucrado DECIMAL(10,2),
    tiempo_ventana_segundos INTEGER,
    
    -- Acción Tomada
    accion TEXT, -- BLOCKED, FLAGGED, NOTIFIED, REVERSED
    resuelto INTEGER DEFAULT 0,
    resuelto_por INTEGER,
    resuelto_fecha TEXT,
    notas TEXT,
    
    FOREIGN KEY(account_id) REFERENCES loyalty_accounts(id),
    FOREIGN KEY(customer_id) REFERENCES customers(id)
);

-- 5. HISTORIAL DE NIVELES (Gamificación)
CREATE TABLE IF NOT EXISTS loyalty_tier_history (
    id BIGSERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    nivel_anterior TEXT,
    nivel_nuevo TEXT NOT NULL,
    fecha_cambio TIMESTAMP DEFAULT NOW(),
    razon TEXT, -- "Alcanzó $5000 en compras"
    
    FOREIGN KEY(customer_id) REFERENCES customers(id)
);

-- ============================================================================
-- ÍNDICES PARA PERFORMANCE
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_loyalty_ledger_customer ON loyalty_ledger(customer_id);
CREATE INDEX IF NOT EXISTS idx_loyalty_ledger_fecha ON loyalty_ledger(fecha_hora);
CREATE INDEX IF NOT EXISTS idx_loyalty_ledger_tipo ON loyalty_ledger(tipo);
CREATE INDEX IF NOT EXISTS idx_loyalty_ledger_ticket ON loyalty_ledger(ticket_referencia_id);

CREATE INDEX IF NOT EXISTS idx_loyalty_rules_activo ON loyalty_rules(activo);
CREATE INDEX IF NOT EXISTS idx_loyalty_rules_vigencia ON loyalty_rules(vigencia_inicio, vigencia_fin);

CREATE INDEX IF NOT EXISTS idx_fraud_log_customer ON loyalty_fraud_log(customer_id);
CREATE INDEX IF NOT EXISTS idx_fraud_log_fecha ON loyalty_fraud_log(fecha_hora);

-- ============================================================================
-- TRIGGERS DE SEGURIDAD
-- ============================================================================

-- Trigger: Actualizar fecha de última actividad en la cuenta
-- PostgreSQL: Los triggers requieren una función
CREATE OR REPLACE FUNCTION update_loyalty_last_activity()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE loyalty_accounts 
    SET fecha_ultima_actividad = NOW()
    WHERE id = NEW.account_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_loyalty_last_activity_trigger ON loyalty_ledger;
CREATE TRIGGER update_loyalty_last_activity_trigger
AFTER INSERT ON loyalty_ledger
FOR EACH ROW
EXECUTE FUNCTION update_loyalty_last_activity();

-- Trigger: Prevenir modificación de ledger (Inmutabilidad)
-- PostgreSQL: Los triggers requieren una función
CREATE OR REPLACE FUNCTION prevent_ledger_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'El ledger de lealtad es inmutable. Use transacciones de ajuste.';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS prevent_ledger_update_trigger ON loyalty_ledger;
CREATE TRIGGER prevent_ledger_update_trigger
BEFORE UPDATE ON loyalty_ledger
FOR EACH ROW
EXECUTE FUNCTION prevent_ledger_update();

-- ============================================================================
-- DATOS INICIALES
-- ============================================================================

-- Regla Base: 1% en todas las compras (DEBE estar activa)
INSERT INTO loyalty_rules (
    regla_id, 
    nombre_display, 
    descripcion, 
    condicion_tipo, 
    multiplicador, 
    prioridad,
    activo
) VALUES (
    'BASE_DEFAULT',
    '1% Base en Todas las Compras',
    'Cashback estándar del 1% aplicable a todas las compras',
    'GLOBAL',
    0.01,
    0,
    1
) ON CONFLICT (regla_id) DO NOTHING;

-- Regla Ejemplo: 10% los fines de semana
INSERT INTO loyalty_rules (
    regla_id,
    nombre_display,
    descripcion,
    condicion_tipo,
    multiplicador,
    prioridad,
    aplica_lunes,
    aplica_martes,
    aplica_miercoles,
    aplica_jueves,
    aplica_viernes
) VALUES (
    'WEEKEND_BOOST',
    '10% Extra en Fines de Semana',
    'Cashback del 10% adicional para compras de sábado y domingo',
    'GLOBAL',
    0.10,
    10,
    0, 0, 0, 0, 0
) ON CONFLICT (regla_id) DO NOTHING;
