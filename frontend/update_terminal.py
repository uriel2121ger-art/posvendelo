import sys

with open('src/renderer/src/Terminal.tsx', 'r') as f:
    content = f.read()

# 1. Update imports
content = content.replace(
    "import { Banknote, Plus, Search as SearchIcon } from 'lucide-react'",
    "import { Banknote, Plus, Search as SearchIcon, X, Package, Percent, Trash2, ShoppingCart, Users, Box, Settings, FileText, ClipboardList, LogOut } from 'lucide-react'"
)

# 2. Extract start text
start_str = "  return (\n    <div className=\"flex h-screen flex-col overflow-hidden bg-zinc-950 font-sans text-slate-200\">"
start_idx = content.find(start_str)

if start_idx == -1:
    print("Could not find return statement start!")
    sys.exit(1)

new_jsx = """  return (
    <div className="flex h-screen flex-col overflow-hidden bg-zinc-950 font-sans text-slate-200 select-none">
      {/* 1. TOP NAVBAR (Eleventa style) */}
      <div className="flex items-center gap-1 bg-zinc-900 border-b border-zinc-800 p-2 overflow-x-auto shrink-0">
        <button className="flex items-center gap-2 px-4 py-2 bg-zinc-800 hover:bg-zinc-700 rounded shadow-sm border border-zinc-700 font-bold text-blue-400">
          <ShoppingCart className="w-5 h-5"/> F1 Ventas
        </button>
        <button className="flex items-center gap-2 px-4 py-2 hover:bg-zinc-800 rounded font-medium text-zinc-400 hover:text-zinc-200 transition-colors">
          <Users className="w-5 h-5"/> F2 Clientes
        </button>
        <button className="flex items-center gap-2 px-4 py-2 hover:bg-zinc-800 rounded font-medium text-zinc-400 hover:text-zinc-200 transition-colors">
          <Box className="w-5 h-5"/> F3 Productos
        </button>
        <button className="flex items-center gap-2 px-4 py-2 hover:bg-zinc-800 rounded font-medium text-zinc-400 hover:text-zinc-200 transition-colors">
          <ClipboardList className="w-5 h-5"/> F4 Inventario
        </button>
        <button className="flex items-center gap-2 px-4 py-2 hover:bg-zinc-800 rounded font-medium text-zinc-400 hover:text-zinc-200 transition-colors">
          <Settings className="w-5 h-5"/> Configuración
        </button>
        <button className="flex items-center gap-2 px-4 py-2 hover:bg-zinc-800 rounded font-medium text-zinc-400 hover:text-zinc-200 transition-colors">
          <FileText className="w-5 h-5"/> Facturas
        </button>

        <div className="ml-auto flex items-center gap-4 bg-zinc-950 px-4 py-1.5 rounded-full border border-zinc-800">
          <div className="text-xs text-zinc-500 text-right">
            <div>Le atiende:</div>
            <div className="font-bold text-zinc-300">Admin</div>
          </div>
          <button className="text-zinc-500 hover:text-zinc-300 transition-colors">
            <LogOut className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* DEV CONFIG (Collapsible) */}
      <details className="bg-zinc-950 border-b border-zinc-900 text-xs shrink-0 group">
        <summary className="p-2 cursor-pointer text-zinc-600 hover:text-zinc-400 list-none flex items-center gap-2 opacity-40 hover:opacity-100 transition-opacity">
          <Settings className="w-3 h-3 group-open:rotate-90 transition-transform" /> Configuración de conexión (Dev)
        </summary>
        <div className="p-4 grid grid-cols-1 md:grid-cols-4 lg:grid-cols-7 gap-4 bg-zinc-900 border-t border-zinc-800">
          <input className="rounded border border-zinc-700 bg-zinc-950 px-3 py-2 text-zinc-300 focus:border-blue-500 focus:outline-none" value={config.baseUrl} onChange={(e) => setConfig((prev) => ({ ...prev, baseUrl: e.target.value }))} placeholder="Base URL" />
          <input className="rounded border border-zinc-700 bg-zinc-950 px-3 py-2 text-zinc-300 focus:border-blue-500 focus:outline-none" value={config.token} onChange={(e) => setConfig((prev) => ({ ...prev, token: e.target.value }))} placeholder="Token" />
          <input className="rounded border border-zinc-700 bg-zinc-950 px-3 py-2 text-zinc-300 focus:border-blue-500 focus:outline-none" type="number" value={config.terminalId} onChange={(e) => setConfig((prev) => ({ ...prev, terminalId: Math.max(1, Number(e.target.value || 1)) }))} placeholder="Terminal ID" />
          <button className="rounded bg-blue-600 px-3 py-2 font-semibold text-white hover:bg-blue-500 disabled:opacity-60 transition-colors" onClick={() => void handleLoadProducts()} disabled={busy}>{busy ? 'Cargando...' : 'Cargar productos'}</button>
          <div className="col-span-3 flex items-center text-amber-400/80 font-medium">{message}</div>
        </div>
      </details>

      {/* 2. SEARCH ROW */}
      <div className="flex items-center gap-4 p-4 bg-zinc-900 border-b border-zinc-800 shrink-0 shadow-sm relative z-10">
        <div className="text-sm font-bold text-zinc-400 whitespace-nowrap">Código del Producto:</div>
        <div className="relative flex-1 max-w-3xl">
          <SearchIcon className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-zinc-400" />
          <input
            autoFocus
            ref={searchInputRef}
            className="w-full rounded-xl border-2 border-blue-500 bg-zinc-950 py-3 pl-12 pr-4 text-xl font-mono focus:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-400 shadow-[0_0_15px_rgba(59,130,246,0.15)] transition-all"
            placeholder="🔍 Escanea o escribe y presiona Enter..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                if (firstMatch) {
                  addProduct(firstMatch)
                  setQuery('')
                }
              }
            }}
          />
        </div>
        <button
          className="flex items-center gap-2 rounded-xl bg-blue-600 px-8 py-3.5 font-bold text-white shadow-[0_0_15px_rgba(37,99,235,0.4)] hover:bg-blue-500 disabled:opacity-50 transition-all hover:scale-[1.02] active:scale-[0.98]"
          onClick={() => {
            if (firstMatch) {
               addProduct(firstMatch)
               setQuery('')
               searchInputRef.current?.focus()
            }
          }}
          disabled={!firstMatch || busy}
        >
          ✓ ADD
          <span className="hidden sm:inline"> - Agregar Producto</span>
        </button>
      </div>

      {/* 3. QUICK ACTIONS ROW */}
      <div className="flex flex-wrap items-center gap-2 px-4 py-3 bg-zinc-900 border-b border-zinc-800 shrink-0">
        <button className="flex items-center gap-1.5 rounded bg-zinc-800 border border-zinc-700 px-4 py-2 text-xs font-semibold text-zinc-300 hover:bg-zinc-700 transition-colors shadow-sm">
          <Plus className="h-4 w-4 text-emerald-400" /> INS Varios
        </button>
        <button 
          className="flex items-center gap-1.5 rounded bg-zinc-800 border border-zinc-700 px-4 py-2 text-xs font-semibold text-zinc-300 hover:bg-zinc-700 transition-colors shadow-sm"
          onClick={addCommonProduct}
        >
          <Package className="h-4 w-4 text-blue-400" /> CTRL+P Art. Común
        </button>
        <button 
          className="flex items-center gap-1.5 rounded bg-zinc-800 border border-zinc-700 px-4 py-2 text-xs font-semibold text-zinc-300 hover:bg-zinc-700 transition-colors shadow-sm"
          onClick={() => { searchInputRef.current?.focus(); searchInputRef.current?.select(); }}
        >
          <SearchIcon className="h-4 w-4 text-amber-400" /> F10 Buscar
        </button>
        <button 
          className="flex items-center gap-1.5 rounded bg-zinc-800 border border-zinc-700 px-4 py-2 text-xs font-semibold text-zinc-300 hover:bg-zinc-700 transition-colors shadow-sm"
          onClick={() => {
            const raw = window.prompt('Descuento global de la nota (%):', String(globalDiscountPct))
            if (raw != null) setGlobalDiscountPct(clampDiscount(Number(raw)))
          }}
        >
          <Percent className="h-4 w-4 text-purple-400" /> F11 Descuento
        </button>
        
        <div className="ml-auto flex items-center gap-3">
           {pendingTickets.length > 0 && (
            <select
              className="rounded-lg border border-amber-700/50 bg-amber-900/20 px-4 py-2 text-xs font-semibold text-amber-400 focus:outline-none cursor-pointer hover:bg-amber-900/40 transition-colors"
              value=""
              onChange={(e) => {
                const value = e.target.value
                if (!value) return
                loadPendingTicket(value)
                e.target.value = ''
              }}
            >
              <option value="">Cargar ticket pendiente... ({pendingTickets.length})</option>
              {pendingTickets.map((ticket) => (
                <option key={ticket.id} value={ticket.id} className="bg-zinc-900 text-amber-400">
                  {ticket.label}
                </option>
              ))}
            </select>
          )}

          <button 
            className="flex items-center gap-1.5 rounded bg-rose-950/40 border border-rose-900/50 px-4 py-2 text-xs font-semibold text-rose-400 hover:bg-rose-900/60 transition-colors disabled:opacity-30 disabled:hover:bg-rose-950/40"
            onClick={deleteSelectedItem}
            disabled={!selectedCartSku}
          >
            <Trash2 className="h-4 w-4" /> DEL Borrar Art.
          </button>
        </div>
      </div>

      {/* 4. TABS ROW */}
      <div className="flex items-end px-4 pt-3 bg-zinc-900 shrink-0">
        <div className="flex gap-1 overflow-x-auto no-scrollbar">
          {activeTickets.map((ticket) => (
            <div
              key={ticket.id}
              className={`group flex items-center gap-3 rounded-t-lg border-t border-l border-r px-5 py-2.5 text-sm font-bold cursor-pointer transition-colors pt-3 ${
                activeTicketId === ticket.id
                  ? 'border-blue-500 bg-zinc-950 text-blue-400'
                  : 'border-zinc-700 bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-zinc-200'
              }`}
              onClick={() => switchActiveTicket(ticket.id)}
            >
              {ticket.label}
              <button 
                className={`rounded border border-transparent p-0.5 opacity-50 hover:border-zinc-500 hover:bg-zinc-600 hover:opacity-100 hover:text-white transition-all ${activeTickets.length > 1 ? 'block' : 'hidden'}`}
                onClick={(e) => {
                  e.stopPropagation()
                  closeActiveTicket(ticket.id)
                }}
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
          <button
            className="flex items-center justify-center rounded-t-lg bg-zinc-800 px-4 py-3 text-zinc-400 hover:bg-zinc-700 hover:text-zinc-200 transition-colors mb-0.5"
            onClick={createNewActiveTicket}
            disabled={activeTickets.length >= 8}
            title="Nuevo ticket activo"
          >
            <Plus className="h-5 w-5" />
          </button>
        </div>
      </div>

      {/* 5. MAIN TABLE */}
      <div className="flex-1 flex flex-col bg-zinc-950 overflow-hidden relative shadow-[inset_0_5px_15px_rgba(0,0,0,0.5)]">
        <div className="grid grid-cols-12 gap-4 border-b border-zinc-800 bg-zinc-900 px-6 py-3 text-xs font-bold uppercase tracking-wider text-zinc-500 shadow-sm z-10 shrink-0">
          <div className="col-span-2">Código de Barras</div>
          <div className="col-span-5">Descripción del Producto</div>
          <div className="col-span-2 text-right">Precio Venta</div>
          <div className="col-span-1 text-center">Cant.</div>
          <div className="col-span-2 text-right">Importe</div>
        </div>

        <div className="flex-1 overflow-y-auto bg-zinc-950 pb-4">
          {cart.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center text-zinc-600">
               <ShoppingCart className="w-20 h-20 mb-6 opacity-10" />
               <p className="text-xl font-medium text-zinc-500">El ticket está vacío</p>
               <p className="text-sm mt-2">Escanea un producto o búscalo por código</p>
            </div>
          ) : (
            cart.map((item) => (
              <div
                key={item.sku}
                onClick={() => setSelectedCartSku(item.sku)}
                className={`grid grid-cols-12 gap-4 border-b px-6 py-4 items-center cursor-pointer transition-colors text-sm relative ${
                  selectedCartSku === item.sku
                    ? 'border-blue-900/40 bg-blue-900/10'
                    : 'border-zinc-900 hover:bg-zinc-900/50'
                }`}
              >
                {selectedCartSku === item.sku && <div className="absolute left-0 w-1 h-full bg-blue-500 top-0"></div>}
                <div className={`col-span-2 font-mono ${selectedCartSku === item.sku ? 'text-blue-400' : 'text-zinc-400'}`}>
                   {item.sku}
                </div>
                <div className={`col-span-5 font-semibold text-lg ${selectedCartSku === item.sku ? 'text-blue-100' : 'text-zinc-200'}`}>
                   {item.name}
                   {item.isCommon && item.commonNote && <span className="ml-2 text-xs font-normal text-amber-400">({item.commonNote})</span>}
                </div>
                <div className={`col-span-2 text-right font-mono text-base ${selectedCartSku === item.sku ? 'text-zinc-200' : 'text-zinc-300'}`}>
                   ${item.price.toFixed(2)}
                </div>
                <div className="col-span-1 flex justify-center">
                  <input
                    className={`w-16 rounded border px-2 py-1.5 text-center font-bold font-mono text-base ${
                      selectedCartSku === item.sku
                        ? 'border-blue-500 bg-blue-900/40 text-white focus:outline-none focus:ring-1 focus:ring-blue-400'
                        : 'border-zinc-700 bg-zinc-800 text-zinc-100 focus:outline-none'
                    }`}
                    type="number"
                    min={1}
                    value={item.qty}
                    onChange={(e) => updateItemQty(item.sku, Number(e.target.value || 1))}
                    onClick={(e) => { e.stopPropagation(); setSelectedCartSku(item.sku); }}
                  />
                </div>
                <div className={`col-span-2 text-right font-mono font-bold text-xl ${selectedCartSku === item.sku ? 'text-blue-400 font-black' : 'text-blue-500/80'}`}>
                   ${item.subtotal.toFixed(2)}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* 6. BOTTOM FOOTER SECTION */}
      <div className="flex flex-col md:flex-row gap-6 bg-zinc-900 border-t border-zinc-800 p-4 shadow-[0_-10px_20px_rgba(0,0,0,0.4)] shrink-0 z-20">
         
         <div className="w-full md:w-2/5 flex flex-col justify-between pt-2">
            <div className="mb-4 text-center md:text-left">
              <span className="text-4xl font-black text-blue-400 mr-3">{cart.length}</span>
              <span className="text-zinc-400 font-medium text-lg uppercase tracking-wide">Productos en Venta.</span>
            </div>
            
            <div className="flex gap-2.5">
              <button 
                className="flex flex-1 flex-col items-center justify-center gap-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 p-3 text-emerald-400 font-bold transition-colors disabled:opacity-50 hover:text-emerald-300 shadow-sm"
                onClick={() => void handleCharge()}
                disabled={busy || cart.length === 0}
              >
                <Banknote className="h-6 w-6" />
                <span className="text-xs tracking-wider">F12 - Cobrar</span>
              </button>
              <button 
                className="flex flex-1 flex-col items-center justify-center gap-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 p-3 text-amber-400 font-bold transition-colors disabled:opacity-50 hover:text-amber-300 shadow-sm"
                onClick={saveCurrentAsPending}
                disabled={busy || cart.length === 0}
              >
                <ShoppingCart className="h-6 w-6" />
                <span className="text-xs tracking-wider">Pendiente</span>
              </button>
              <button 
                className="flex flex-1 flex-col items-center justify-center gap-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 p-3 text-rose-400 font-bold transition-colors disabled:opacity-50 hover:text-rose-300 shadow-sm"
                onClick={deleteSelectedItem}
                disabled={!selectedCartSku}
              >
                <Trash2 className="h-6 w-6" />
                <span className="text-xs tracking-wider">Eliminar</span>
              </button>
            </div>
         </div>

         <div className="flex-1 rounded-xl bg-zinc-950 border border-zinc-800 flex items-stretch overflow-hidden shadow-inner">
            <div className="flex-1 p-6 flex flex-col justify-center space-y-4">
               <div className="flex justify-between items-end border-b border-zinc-900 pb-2">
                 <span className="text-sm font-bold uppercase tracking-wider text-zinc-500">Cliente / Tipo de Pago:</span>
                 <div className="flex items-center gap-3">
                    <input className="bg-transparent text-right font-medium text-zinc-300 focus:outline-none w-32 border-b border-zinc-800 focus:border-blue-500 transition-colors" value={customerName} onChange={e => setCustomerName(e.target.value)} placeholder="Público General" />
                    <select className="bg-zinc-900 border border-zinc-700 rounded text-zinc-300 py-1.5 px-2 focus:outline-none font-medium hover:border-zinc-500 transition-colors cursor-pointer" value={paymentMethod} onChange={e => setPaymentMethod(e.target.value as PaymentMethod)}>
                       <option value="cash">Efectivo</option>
                       <option value="card">Tarjeta</option>
                       <option value="transfer">Transf.</option>
                    </select>
                 </div>
               </div>
               
               {globalDiscountPct > 0 && (
                 <div className="flex justify-between items-end border-b border-zinc-900 pb-2">
                   <span className="text-sm font-bold uppercase tracking-wider text-purple-400/80">Descuento Global ({globalDiscountPct}%):</span>
                   <span className="text-lg font-mono font-bold text-purple-400">-${totals.globalDiscountAmount.toFixed(2)}</span>
                 </div>
               )}

               <div className="flex justify-between items-end">
                 <span className="text-sm font-bold uppercase tracking-wider text-zinc-500">Pago Con:</span>
                 {paymentMethod === 'cash' ? (
                   <input
                     className="w-40 bg-transparent text-right font-mono text-3xl font-bold text-emerald-400 border-b-2 border-zinc-800 focus:border-emerald-500 outline-none transition-colors"
                     type="number"
                     min={0}
                     value={amountReceived}
                     onChange={(e) => setAmountReceived(e.target.value)}
                     placeholder="0.00"
                   />
                 ) : (
                   <span className="text-3xl font-mono font-bold text-emerald-400">{paymentMethod.toUpperCase()}</span>
                 )}
               </div>
               
               <div className="flex justify-between items-end">
                 <span className="text-sm font-bold uppercase tracking-wider text-zinc-500 hidden md:block">Cambio:</span>
                 <span className="text-sm font-bold uppercase tracking-wider text-zinc-500 md:hidden">C:</span>
                 <span className={`text-3xl font-mono font-bold ${paymentMethod === 'cash' ? 'text-amber-400' : 'text-zinc-600'}`}>
                   ${paymentMethod === 'cash' ? changeDue.toFixed(2) : '0.00'}
                 </span>
               </div>
            </div>
            
            <div className="w-[35%] min-w-[220px] bg-blue-900/10 border-l border-zinc-800 p-8 flex flex-col justify-center items-end relative overflow-hidden group">
               <div className="absolute inset-0 bg-gradient-to-br from-blue-900/5 to-transparent z-0"></div>
               <div className="text-sm font-bold uppercase tracking-widest text-blue-500/50 mb-2 z-10 transition-colors group-hover:text-blue-500/70">Total a Pagar</div>
               <span className="text-4xl md:text-5xl lg:text-6xl font-mono font-black text-blue-400 tracking-tighter drop-shadow-[0_0_15px_rgba(59,130,246,0.2)] z-10 group-hover:scale-105 transition-transform origin-right">
                 ${totals.total.toFixed(2)}
               </span>
               <div className="absolute -bottom-16 -right-16 text-blue-500/5 group-hover:text-blue-500/10 transition-colors">
                  <Banknote className="w-56 h-56" />
               </div>
            </div>
         </div>
      </div>
    </div>
  )
}
"""

content = content[:start_idx] + new_jsx

with open('src/renderer/src/Terminal.tsx', 'w') as f:
    f.write(content)

print("Update complete!")
