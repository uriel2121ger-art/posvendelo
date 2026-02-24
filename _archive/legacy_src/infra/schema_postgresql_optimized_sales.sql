-- =============================================================================
-- OPTIMIZACIONES PARA IDENTIFICACIÓN DE VENTAS POR PC/TERMINAL
-- =============================================================================
-- Este archivo contiene índices, vistas y funciones optimizadas para
-- identificar rápidamente de qué PC/terminal proviene cada venta.
-- =============================================================================

-- =============================================================================
-- 1. ÍNDICES OPTIMIZADOS
-- =============================================================================

-- Índice para búsquedas rápidas por pos_id (terminal/PC)
CREATE INDEX IF NOT EXISTS idx_sales_pos_id ON sales(pos_id) 
WHERE pos_id IS NOT NULL;

-- Índice compuesto para búsquedas por sucursal y terminal
CREATE INDEX IF NOT EXISTS idx_sales_branch_pos ON sales(branch_id, pos_id) 
WHERE pos_id IS NOT NULL;

-- Índice para búsquedas por branch_id (sucursal)
CREATE INDEX IF NOT EXISTS idx_sales_branch_id ON sales(branch_id);

-- Índice compuesto para búsquedas por terminal y timestamp (muy común)
CREATE INDEX IF NOT EXISTS idx_sales_pos_timestamp ON sales(pos_id, timestamp) 
WHERE pos_id IS NOT NULL AND status = 'completed';

-- Índice para búsquedas por terminal de sincronización
CREATE INDEX IF NOT EXISTS idx_sales_synced_from ON sales(synced_from_terminal) 
WHERE synced_from_terminal IS NOT NULL;

-- Índice compuesto para búsquedas por sucursal, terminal y fecha
CREATE INDEX IF NOT EXISTS idx_sales_branch_pos_date ON sales(branch_id, pos_id, created_at) 
WHERE pos_id IS NOT NULL AND status = 'completed';

-- Índice para búsquedas por turn_id (relación con terminal)
CREATE INDEX IF NOT EXISTS idx_turns_terminal_branch ON turns(terminal_id, branch_id);

-- Índice para búsquedas por terminal_id en turns
CREATE INDEX IF NOT EXISTS idx_turns_terminal_id ON turns(terminal_id);

-- =============================================================================
-- 2. VISTA OPTIMIZADA: VENTAS CON IDENTIFICACIÓN DE ORIGEN
-- =============================================================================

CREATE OR REPLACE VIEW v_sales_with_origin AS
SELECT 
    -- Información básica de la venta
    s.id AS sale_id,
    s.uuid,
    s.timestamp,
    s.created_at,
    s.updated_at,
    s.total,
    s.subtotal,
    s.tax,
    s.discount,
    s.status,
    
    -- IDENTIFICACIÓN DEL TERMINAL/PC (prioridad: pos_id > terminal_id > synced_from)
    COALESCE(
        s.pos_id,                                    -- Primera opción: pos_id directo
        'T' || t.terminal_id::TEXT,                  -- Segunda opción: terminal_id del turno
        s.synced_from_terminal,                      -- Tercera opción: terminal de sincronización
        'DESCONOCIDO'                                -- Fallback
    ) AS terminal_identifier,
    
    -- Información detallada del terminal
    s.pos_id AS pos_id_sale,                         -- POS ID en la venta
    t.terminal_id,                                   -- ID numérico del terminal
    t.pos_id AS pos_id_turn,                         -- POS ID en el turno
    s.synced_from_terminal,                          -- Terminal de sincronización
    
    -- Información de sucursal
    s.branch_id,
    b.name AS branch_name,
    b.code AS branch_code,
    
    -- Información del turno
    s.turn_id,
    t.start_timestamp AS turn_start,
    t.end_timestamp AS turn_end,
    
    -- Información del usuario
    s.user_id,
    u.username,
    u.name AS user_name,
    
    -- Información del cliente
    s.customer_id,
    c.name AS customer_name,
    
    -- Información fiscal
    s.serie,
    s.folio_visible,
    
    -- Método de pago
    s.payment_method,
    
    -- Información de sincronización
    s.synced,
    s.sync_status
    
FROM sales s
LEFT JOIN turns t ON s.turn_id = t.id
LEFT JOIN branches b ON s.branch_id = b.id
LEFT JOIN users u ON s.user_id = u.id
LEFT JOIN customers c ON s.customer_id = c.id
WHERE s.visible = 1;

-- Comentario en la vista
COMMENT ON VIEW v_sales_with_origin IS 
'Vista optimizada que identifica el origen (PC/terminal) de cada venta. 
Incluye timestamp y toda la información relevante para rastrear ventas por terminal.';

-- =============================================================================
-- 3. FUNCIONES ÚTILES
-- =============================================================================

-- Función: Obtener ventas de un terminal específico
CREATE OR REPLACE FUNCTION get_sales_by_terminal(
    p_terminal_id TEXT,
    p_branch_id INTEGER DEFAULT NULL,
    p_start_date TIMESTAMP DEFAULT NULL,
    p_end_date TIMESTAMP DEFAULT NULL
)
RETURNS TABLE (
    sale_id BIGINT,
    uuid TEXT,
    timestamp TEXT,
    created_at TIMESTAMP,
    terminal_identifier TEXT,
    branch_name TEXT,
    total DOUBLE PRECISION,
    user_name TEXT,
    customer_name TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        v.sale_id,
        v.uuid,
        v.timestamp,
        v.created_at,
        v.terminal_identifier,
        v.branch_name,
        v.total,
        v.user_name,
        v.customer_name
    FROM v_sales_with_origin v
    WHERE v.terminal_identifier = p_terminal_id
        AND (p_branch_id IS NULL OR v.branch_id = p_branch_id)
        AND (p_start_date IS NULL OR v.created_at >= p_start_date)
        AND (p_end_date IS NULL OR v.created_at <= p_end_date)
        AND v.status = 'completed'
    ORDER BY v.created_at DESC;
END;
$$ LANGUAGE plpgsql;

-- Función: Resumen de ventas por terminal
CREATE OR REPLACE FUNCTION get_sales_summary_by_terminal(
    p_start_date TIMESTAMP DEFAULT NULL,
    p_end_date TIMESTAMP DEFAULT NULL
)
RETURNS TABLE (
    terminal_identifier TEXT,
    branch_name TEXT,
    branch_code TEXT,
    total_ventas BIGINT,
    total_monto DOUBLE PRECISION,
    primera_venta TIMESTAMP,
    ultima_venta TIMESTAMP,
    promedio_venta DOUBLE PRECISION
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        v.terminal_identifier,
        v.branch_name,
        v.branch_code,
        COUNT(*)::BIGINT AS total_ventas,
        SUM(v.total) AS total_monto,
        MIN(v.created_at) AS primera_venta,
        MAX(v.created_at) AS ultima_venta,
        AVG(v.total) AS promedio_venta
    FROM v_sales_with_origin v
    WHERE v.status = 'completed'
        AND (p_start_date IS NULL OR v.created_at >= p_start_date)
        AND (p_end_date IS NULL OR v.created_at <= p_end_date)
    GROUP BY v.terminal_identifier, v.branch_name, v.branch_code
    ORDER BY v.branch_name, v.terminal_identifier;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- 4. CONSULTAS OPTIMIZADAS DE EJEMPLO
-- =============================================================================

-- Ejemplo 1: Ventas de un terminal específico (más rápida)
-- Uso: SELECT * FROM get_sales_by_terminal('PC1', 1, '2026-01-01', '2026-01-31');

-- Ejemplo 2: Resumen de todas las ventas por terminal
-- Uso: SELECT * FROM get_sales_summary_by_terminal('2026-01-01', '2026-01-31');

-- Ejemplo 3: Consulta directa optimizada (usando la vista)
/*
SELECT 
    sale_id,
    timestamp,
    created_at,
    terminal_identifier,
    branch_name,
    total,
    user_name
FROM v_sales_with_origin
WHERE terminal_identifier = 'PC1'
    AND branch_id = 1
    AND created_at >= '2026-01-01'
    AND created_at <= '2026-01-31'
    AND status = 'completed'
ORDER BY created_at DESC
LIMIT 100;
*/

-- Ejemplo 4: Ventas por terminal con timestamp (consulta rápida)
/*
SELECT 
    terminal_identifier,
    branch_name,
    COUNT(*) AS total_ventas,
    SUM(total) AS total_monto,
    MIN(created_at) AS primera_venta,
    MAX(created_at) AS ultima_venta
FROM v_sales_with_origin
WHERE status = 'completed'
    AND created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY terminal_identifier, branch_name
ORDER BY branch_name, terminal_identifier;
*/

-- =============================================================================
-- 5. ACTUALIZACIÓN DE ESTADÍSTICAS
-- =============================================================================

-- Actualizar estadísticas de la tabla sales (ejecutar periódicamente)
-- ANALYZE sales;
-- ANALYZE turns;
-- ANALYZE branches;

-- =============================================================================
-- NOTAS DE OPTIMIZACIÓN
-- =============================================================================
-- 1. Los índices parciales (WHERE) mejoran el rendimiento al reducir el tamaño
-- 2. La vista materializada podría ser útil si las consultas son muy frecuentes
-- 3. Las funciones permiten reutilizar consultas complejas
-- 4. Siempre usar created_at para filtros de fecha (más eficiente que timestamp TEXT)
-- 5. Los índices compuestos mejoran consultas que filtran por múltiples campos
-- =============================================================================
