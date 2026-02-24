-- Migration: Add branch_ticket_config table for multi-branch ticket design
-- Date: 2025-12-10
-- Purpose: Store ticket configuration per branch for customized ticket printing

CREATE TABLE IF NOT EXISTS branch_ticket_config (
    branch_id INTEGER PRIMARY KEY,
    -- Business Information
    business_name TEXT NOT NULL,
    business_address TEXT,
    business_phone TEXT,
    business_rfc TEXT,
    website_url TEXT,
    
    -- Ticket Content Options
    show_phone INTEGER DEFAULT 1,
    show_rfc INTEGER DEFAULT 1,
    show_product_code INTEGER DEFAULT 0,
    show_unit INTEGER DEFAULT 0,
    
    -- Formatting
    price_decimals INTEGER DEFAULT 2,
    currency_symbol TEXT DEFAULT '$',
    show_separators INTEGER DEFAULT 1,
    line_spacing REAL DEFAULT 1.0,
    margin_chars INTEGER DEFAULT 0,
    
    -- Messages
    thank_you_message TEXT DEFAULT '¡Gracias por su compra!',
    legal_text TEXT,
    
    -- QR Code
    qr_enabled INTEGER DEFAULT 0,
    qr_content_type TEXT DEFAULT 'url', -- 'url' or 'folio'
    
    -- Print Options
    cut_lines INTEGER DEFAULT 3,
    bold_headers INTEGER DEFAULT 1,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY(branch_id) REFERENCES branches(id)
);

CREATE INDEX IF NOT EXISTS idx_ticket_config_branch ON branch_ticket_config(branch_id);
