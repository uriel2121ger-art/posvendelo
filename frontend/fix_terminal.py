import re

fpath = 'src/renderer/src/Terminal.tsx'

with open(fpath, 'r') as f:
    text = f.read()

# 1. Add TopNavbar Import
if "import TopNavbar" not in text:
    text = text.replace("import type { ReactElement } from 'react'", "import type { ReactElement } from 'react'\nimport TopNavbar from './components/TopNavbar'")

# 2. Add TopNavbar component, remove the raw H2 title
# <div className="border-b border-zinc-800 bg-zinc-900 p-4">
#   <h2 className="mb-3 text-xl font-bold text-blue-300">
#     Terminal POS - Migracion PyQt6 (fase 2)
#   </h2>
#   <div className="grid grid-cols-1 gap-2 md:grid-cols-7">
text = re.sub(
    r'<div className="border-b border-zinc-800 bg-zinc-900 p-4">\s*<h2 className="mb-3 text-xl font-bold text-blue-300">.*?</h2>',
    '<TopNavbar />\n      <div className="border-b border-zinc-800 bg-zinc-900/80 p-5 mt-4 shadow-sm rounded-xl mx-4 mb-2">\n        <h2 className="mb-4 text-xl font-bold text-blue-400 px-1">Configuración y Recepción</h2>',
    text,
    flags=re.DOTALL
)

# 3. Class Replacements
new_input = 'className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"'
text = text.replace('className="rounded border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm"', new_input)
text = text.replace('className="w-full rounded border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm"', new_input)

# Small Search and Qty mapping
text = text.replace(
    'className="w-full rounded border border-zinc-700 bg-zinc-950 py-2 pl-9 pr-3"',
    'className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 pl-10 pr-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"'
)
text = text.replace(
    'className="w-24 rounded border border-zinc-700 bg-zinc-950 px-3 py-2 text-center"',
    'className="w-32 rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold text-center focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"'
)

# Base Buttons
new_btn_blue = 'className="flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 font-bold text-white shadow-[0_0_15px_rgba(37,99,235,0.2)] hover:bg-blue-500 hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:hover:translate-y-0"'
text = text.replace('className="rounded bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-500 disabled:opacity-60"', new_btn_blue)
text = text.replace('className="flex items-center justify-center gap-2 rounded bg-blue-600 px-4 py-2 font-semibold text-white hover:bg-blue-500 disabled:opacity-60"', new_btn_blue)

new_btn_zinc = 'className="flex items-center justify-center gap-2 rounded-xl bg-zinc-800 border border-zinc-700 px-5 py-2.5 font-bold text-zinc-300 shadow-sm hover:bg-zinc-700 hover:text-white transition-all disabled:opacity-50"'
text = text.replace('className="rounded bg-zinc-700 px-3 py-2 text-sm font-semibold hover:bg-zinc-600 disabled:opacity-60"', new_btn_zinc)

new_btn_red = 'className="flex items-center justify-center gap-2 rounded-xl bg-rose-500/20 border border-rose-500/30 px-5 py-2.5 font-bold text-rose-400 shadow-[0_0_15px_rgba(243,66,102,0.1)] hover:bg-rose-500/40 hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:hover:translate-y-0"'
text = text.replace('className="rounded bg-red-700 px-3 py-2 text-sm font-semibold hover:bg-red-600 disabled:opacity-60"', new_btn_red)

# Specific terminal checkout button
text = text.replace(
    'className="flex w-full items-center justify-center gap-2 rounded bg-blue-600 py-2 font-bold text-white hover:bg-blue-500 disabled:opacity-60"',
    'className="flex w-full mt-4 items-center justify-center gap-2 rounded-xl bg-blue-600 py-4 font-bold text-lg tracking-wide text-white shadow-[0_0_20px_rgba(37,99,235,0.4)] hover:bg-blue-500 hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:hover:translate-y-0 disabled:shadow-none"'
)

# Panels
text = re.sub(
    r'className="grid grid-cols-1(.*?)border-b border-zinc-800 bg-zinc-900(.*?)p-4(.*?)"',
    r'className="grid grid-cols-1\1border-b border-zinc-800 bg-zinc-900/80 p-5 mt-2 shadow-sm rounded-xl mx-4\3"',
    text
)

# Table headers inside terminal
text = text.replace(
    'className="grid flex-1 grid-cols-1 gap-4 overflow-hidden p-4 md:grid-cols-[1fr_360px]"',
    'className="grid flex-1 grid-cols-1 gap-4 overflow-hidden p-6 bg-zinc-950 shadow-[inset_0_5px_15px_rgba(0,0,0,0.3)] md:grid-cols-[1fr_400px]"'
)

text = text.replace(
    'className="grid grid-cols-12 gap-2 bg-zinc-900 px-4 py-2 text-xs uppercase text-zinc-400"',
    'className="grid grid-cols-12 gap-2 border-b border-zinc-800 bg-zinc-900/80 px-4 py-3 text-xs font-bold uppercase tracking-wider text-zinc-500"'
)

text = text.replace(
    'className="grid w-full grid-cols-12 gap-2 border-b border-zinc-900 px-4 py-2 text-left text-sm hover:bg-zinc-900"',
    'className="grid w-full grid-cols-12 gap-2 border-b border-zinc-800/50 px-4 py-4 text-left text-sm cursor-pointer transition-colors hover:bg-zinc-800/40"'
)

# Small inputs within ticket row
text = text.replace(
    'className="w-20 rounded border border-zinc-700 bg-zinc-900 px-2 py-1"',
    'className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-2 py-1.5 font-semibold text-blue-300 focus:border-blue-500 focus:outline-none"'
)

with open(fpath, 'w') as f:
    f.write(text)

print("Terminal UI patched.")
