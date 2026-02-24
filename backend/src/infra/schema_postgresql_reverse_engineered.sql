-- Schema generado por ingeniería inversa
-- Fecha: 2026-01-23 00:00:44
-- Base de datos: titan_pos

-- Funciones

-- Función: prevent_negative_stock
CREATE OR REPLACE FUNCTION public.prevent_negative_stock()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
        BEGIN
            IF NEW.stock < 0 THEN
                RAISE EXCEPTION 'Stock cannot be negative';
            END IF;
            RETURN NEW;
        END;
        $function$

