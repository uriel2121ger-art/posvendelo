class FakeCore:
    """Mock Core object to pass to legacy services that expect `self.core.db`"""
    def __init__(self, db):
        self.db = db
        
    async def get_app_config(self):
        """Returns mock app config"""
        return {}
        
    async def get_fiscal_config(self):
        """Returns standard fiscal config from DB"""
        rows = await self.db.execute_query("SELECT * FROM fiscal_config WHERE branch_id = 1 LIMIT 1")
        return dict(rows[0]) if rows else {}

    async def get_sale_details(self, sale_id: int):
        """Fetches sale details"""
        sale = await self.db.execute_query("SELECT * FROM sales WHERE id = %s", (sale_id,))
        if not sale: return None
        
        sale_data = dict(sale[0])
        
        items = await self.db.execute_query("SELECT * FROM sale_items WHERE sale_id = %s", (sale_id,))
        sale_data['items'] = [dict(i) for i in items] if items else []
        
        return sale_data
        
    async def update_fiscal_config(self, updates: dict):
        """Updates fiscal config"""
        pass
        
    async def list_cfdi(self, date_from=None, date_to=None):
        """List CFDIs"""
        return await self.db.execute_query("SELECT * FROM cfdis")
