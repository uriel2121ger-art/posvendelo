"""
SAT Catalog - Reduced catalog of common ClaveProdServ and ClaveUnidad codes
for CFDI 4.0 electronic invoicing in Mexico.

This is a reduced version with ~100 most common codes.
Full catalog has 50,000+ entries.
"""

# Most common ClaveUnidad codes
CLAVES_UNIDAD = [
    ('H87', 'Pieza'),
    ('KGM', 'Kilogramo'),
    ('LTR', 'Litro'),
    ('MTR', 'Metro'),
    ('MTK', 'Metro cuadrado'),
    ('MTQ', 'Metro cúbico'),
    ('XBX', 'Caja'),
    ('XPK', 'Paquete'),
    ('ACT', 'Actividad'),
    ('E48', 'Unidad de servicio'),
    ('GRM', 'Gramo'),
    ('MLT', 'Mililitro'),
    ('XUN', 'Unidad'),
    ('SET', 'Conjunto'),
    ('PR', 'Par'),
    ('DPC', 'Docena de piezas'),
    ('XRO', 'Rollo'),
    ('XBG', 'Bolsa'),
    ('XCT', 'Cartón'),
    ('XPL', 'Cubeta'),
]

# Most common ClaveProdServ codes by category
CLAVES_PROD_SERV = {
    # Generic/Default
    'general': [
        ('01010101', 'No existe en el catálogo'),
    ],
    
    # Abarrotes y alimentos
    'abarrotes': [
        ('50101500', 'Frutas'),
        ('50101700', 'Verduras frescas'),
        ('50102300', 'Lácteos'),
        ('50112000', 'Carne y aves'),
        ('50131600', 'Pan y productos de panadería'),
        ('50151500', 'Aceites y grasas comestibles'),
        ('50161800', 'Bebidas no alcohólicas'),
        ('50171900', 'Cereales'),
        ('50181900', 'Botanas'),
        ('50192100', 'Productos enlatados'),
        ('50201700', 'Especias y condimentos'),
        ('50202201', 'Café'),
        ('50161700', 'Refrescos'),
        ('50171550', 'Azúcar'),
        ('50161509', 'Agua embotellada'),
    ],
    
    # Ferretería y construcción
    'ferreteria': [
        ('30111600', 'Cemento y cal'),
        ('30131500', 'Bloques y ladrillos'),
        ('31162800', 'Clavos y tornillos'),
        ('31162900', 'Tuercas'),
        ('27111700', 'Herramientas de mano'),
        ('31211500', 'Pinturas'),
        ('40141700', 'Tubería PVC'),
        ('26121600', 'Cables eléctricos'),
        ('39121700', 'Lámparas'),
    ],
    
    # Ropa y calzado
    'ropa': [
        ('53101500', 'Camisas y blusas'),
        ('53101600', 'Pantalones'),
        ('53101800', 'Ropa interior'),
        ('53111500', 'Zapatos'),
        ('53111600', 'Botas'),
        ('53102500', 'Uniformes'),
    ],
    
    # Electrónica
    'electronica': [
        ('43211500', 'Computadoras'),
        ('43211700', 'Notebooks'),
        ('43211800', 'Tablets'),
        ('43191500', 'Teléfonos móviles'),
        ('43212100', 'Impresoras'),
        ('52161505', 'Televisores'),
        ('43191600', 'Accesorios de telefonía'),
    ],
    
    # Farmacia y salud
    'farmacia': [
        ('51241500', 'Medicamentos de venta libre'),
        ('42311500', 'Vendajes y gasas'),
        ('42142900', 'Productos de primeros auxilios'),
        ('51181500', 'Vitaminas y suplementos'),
        ('51191600', 'Analgésicos'),
    ],
    
    # ─────────────────────────────────────────────────────────────
    # COSMÉTICOS, SKINCARE, PERFUMES, MAQUILLAJE
    # ─────────────────────────────────────────────────────────────
    'cosmeticos': [
        # Skincare / Cuidado de la piel
        ('53131500', 'Productos para el cuidado de la piel'),
        ('53131501', 'Cremas faciales'),
        ('53131502', 'Cremas corporales'),
        ('53131503', 'Lociones'),
        ('53131504', 'Protector solar'),
        ('53131505', 'Exfoliantes'),
        ('53131506', 'Mascarillas faciales'),
        ('53131507', 'Sérum facial'),
        ('53131508', 'Tónicos faciales'),
        ('53131509', 'Contorno de ojos'),
        ('53131510', 'Limpiadores faciales'),
        
        # Maquillaje
        ('53131600', 'Productos de maquillaje'),
        ('53131601', 'Base de maquillaje'),
        ('53131602', 'Polvo facial'),
        ('53131603', 'Rubor / Blush'),
        ('53131604', 'Sombras de ojos'),
        ('53131605', 'Delineador de ojos'),
        ('53131606', 'Rímel / Máscara de pestañas'),
        ('53131607', 'Labiales'),
        ('53131608', 'Brillo labial / Gloss'),
        ('53131609', 'Corrector / Concealer'),
        ('53131610', 'Iluminador / Highlighter'),
        ('53131611', 'Contorno / Bronzer'),
        ('53131612', 'Primer / Prebase'),
        ('53131613', 'Setting spray'),
        ('53131614', 'Brochas de maquillaje'),
        ('53131615', 'Esponjas de maquillaje'),
        
        # Perfumes y fragancias
        ('53131700', 'Perfumes y fragancias'),
        ('53131701', 'Perfume de mujer'),
        ('53131702', 'Perfume de hombre'),
        ('53131703', 'Agua de colonia'),
        ('53131704', 'Body mist'),
        ('53131705', 'Desodorante'),
        ('53131706', 'Antitranspirante'),
        
        # Cabello / Hair care
        ('53131800', 'Productos para el cabello'),
        ('53131801', 'Shampoo'),
        ('53131802', 'Acondicionador'),
        ('53131803', 'Tratamiento capilar'),
        ('53131804', 'Mascarilla capilar'),
        ('53131805', 'Aceite para cabello'),
        ('53131806', 'Tinte para cabello'),
        ('53131807', 'Gel para cabello'),
        ('53131808', 'Mousse para cabello'),
        ('53131809', 'Spray fijador'),
        ('53131810', 'Plancha para cabello'),
        ('53131811', 'Secadora de cabello'),
        ('53131812', 'Rizador de cabello'),
        
        # Uñas
        ('53131900', 'Productos para uñas'),
        ('53131901', 'Esmalte de uñas'),
        ('53131902', 'Removedor de esmalte'),
        ('53131903', 'Uñas postizas'),
        ('53131904', 'Gel para uñas'),
        ('53131905', 'Acrílico para uñas'),
        ('53131906', 'Lima de uñas'),
        ('53131907', 'Cortauñas'),
        
        # Cuidado personal
        ('53132000', 'Productos de higiene personal'),
        ('53132001', 'Jabón corporal'),
        ('53132002', 'Gel de baño'),
        ('53132003', 'Crema de afeitar'),
        ('53132004', 'Rastrillos / Afeitadoras'),
        ('53132005', 'Pasta dental'),
        ('53132006', 'Enjuague bucal'),
        ('53132007', 'Hilo dental'),
        ('53132008', 'Cepillo dental'),
    ],
    
    # Servicios
    'servicios': [
        ('84111506', 'Servicios de facturación'),
        ('80111500', 'Servicios de asesoría'),
        ('80111600', 'Servicios de consultoría'),
        ('81112100', 'Servicios de mantenimiento'),
        ('90111800', 'Servicios de alimentación'),
        ('91111800', 'Servicios personales'),
        ('91111801', 'Servicio de maquillaje'),
        ('91111802', 'Servicio de peinado'),
        ('91111803', 'Manicure'),
        ('91111804', 'Pedicure'),
        ('91111805', 'Tratamiento facial'),
        ('91111806', 'Masaje'),
        ('91111807', 'Depilación'),
    ],
    
    # Papelería y oficina
    'papeleria': [
        ('44121600', 'Papel'),
        ('44121700', 'Cuadernos'),
        ('44121800', 'Sobres'),
        ('44111500', 'Bolígrafos'),
        ('44121500', 'Carpetas'),
        ('44111900', 'Lápices'),
    ],
    
    # Limpieza
    'limpieza': [
        ('47131800', 'Productos de limpieza'),
        ('47131700', 'Jabones'),
        ('47131600', 'Detergentes'),
        ('47131500', 'Desinfectantes'),
    ],
    
    # Automotriz
    'automotriz': [
        ('25191500', 'Aceites lubricantes'),
        ('25171900', 'Filtros automotrices'),
        ('25172300', 'Frenos'),
        ('25172100', 'Baterías automotrices'),
    ],
    
    # Bebés
    'bebes': [
        ('53111900', 'Ropa de bebé'),
        ('42231500', 'Pañales'),
        ('42231600', 'Toallitas húmedas'),
        ('50192200', 'Fórmula para bebé'),
        ('42231700', 'Biberones'),
        ('42231800', 'Chupones'),
    ],
    
    # Mascotas
    'mascotas': [
        ('10121500', 'Alimento para perros'),
        ('10121600', 'Alimento para gatos'),
        ('10151700', 'Accesorios para mascotas'),
        ('10151800', 'Juguetes para mascotas'),
    ],
}

def get_all_claves_prod_serv():
    """Return flat list of all ClaveProdServ codes."""
    all_codes = []
    for category, codes in CLAVES_PROD_SERV.items():
        all_codes.extend(codes)
    return all_codes

def search_clave_prod_serv(query: str):
    """
    Search for ClaveProdServ by code or description.
    
    Args:
        query: Search term (code or description text)
        
    Returns:
        List of (code, description) tuples matching the query
    """
    query = query.lower().strip()
    results = []
    
    for category, codes in CLAVES_PROD_SERV.items():
        for code, desc in codes:
            if query in code.lower() or query in desc.lower():
                results.append((code, desc, category))
    
    return results

def get_claves_unidad():
    """Return list of ClaveUnidad codes."""
    return CLAVES_UNIDAD

def search_clave_unidad(query: str):
    """
    Search for ClaveUnidad by code or description.
    
    Args:
        query: Search term
        
    Returns:
        List of (code, description) tuples matching the query
    """
    query = query.lower().strip()
    return [(code, desc) for code, desc in CLAVES_UNIDAD 
            if query in code.lower() or query in desc.lower()]
