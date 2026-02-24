import glob
import re

def remove_header(text):
    start_str = '<div className="border-b border-zinc-800 bg-zinc-900 px-4 py-3">'
    start_idx = text.find(start_str)
    if start_idx == -1: return text

    depth = 0
    i = start_idx
    while i < len(text):
        if text.startswith('<div', i):
            depth += 1
            i += 4
        elif text.startswith('</div', i):
            depth -= 1
            if depth == 0:
                end_idx = text.find('>', i) + 1
                return text[:start_idx] + text[end_idx:]
            i += 5
        else:
            i += 1
    return text

def replace_table_row(match):
    inner = match.group(1)
    inner = inner.replace("bg-zinc-800/80", "bg-blue-900/20 border-l-4 border-blue-500")
    inner = inner.replace("hover:bg-zinc-900", "hover:bg-zinc-800/40")
    return f'className={{`border-b border-zinc-800/50 cursor-pointer transition-colors text-sm ${{ {inner} }}`}}'

def replace_action_bar(match):
    prefix = match.group(1)
    return f'className="grid grid-cols-1{prefix}border-b border-zinc-800 bg-zinc-900/80 p-5 mt-2 shadow-sm rounded-xl mx-4"'


files = glob.glob('src/renderer/src/*Tab.tsx')

old_wrapper = 'className="flex h-screen flex-col bg-zinc-950 text-zinc-100"'
new_wrapper = 'className="flex h-screen flex-col overflow-hidden bg-zinc-950 font-sans text-slate-200 select-none"'

old_input = 'className="rounded border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm"'
new_input = 'className="w-full rounded-xl border-2 border-zinc-800 bg-zinc-900/50 py-2.5 px-4 font-semibold focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder:text-zinc-600 placeholder:font-normal"'

old_full_input = 'className="w-full rounded border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm"'

old_btn_blue = 'className="rounded bg-blue-600 px-3 py-2 text-sm font-semibold hover:bg-blue-500 disabled:opacity-60"'
new_btn_blue = 'className="flex items-center justify-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 font-bold text-white shadow-[0_0_15px_rgba(37,99,235,0.2)] hover:bg-blue-500 hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:hover:translate-y-0"'

old_btn_zinc = 'className="rounded bg-zinc-700 px-3 py-2 text-sm font-semibold hover:bg-zinc-600 disabled:opacity-60"'
new_btn_zinc = 'className="flex items-center justify-center gap-2 rounded-xl bg-zinc-800 border border-zinc-700 px-5 py-2.5 font-bold text-zinc-300 shadow-sm hover:bg-zinc-700 hover:text-white transition-all disabled:opacity-50"'

old_btn_amber = 'className="rounded bg-amber-700 px-3 py-2 text-sm font-semibold hover:bg-amber-600 disabled:opacity-60"'
new_btn_amber = 'className="flex items-center justify-center gap-2 rounded-xl bg-amber-600/20 border border-amber-500/30 px-5 py-2.5 font-bold text-amber-400 shadow-[0_0_15px_rgba(245,158,11,0.1)] hover:bg-amber-600/40 hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:hover:translate-y-0"'

old_btn_red = 'className="rounded bg-red-700 px-3 py-2 text-sm font-semibold hover:bg-red-600 disabled:opacity-60"'
new_btn_red = 'className="flex items-center justify-center gap-2 rounded-xl bg-rose-500/20 border border-rose-500/30 px-5 py-2.5 font-bold text-rose-400 shadow-[0_0_15px_rgba(243,66,102,0.1)] hover:bg-rose-500/40 hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:hover:translate-y-0"'

old_tr_header = 'className="border-b border-zinc-700 text-left text-zinc-400"'
new_tr_header = 'className="border-b border-zinc-800 bg-zinc-900/80 text-left text-xs font-bold uppercase tracking-wider text-zinc-500 shadow-sm"'

old_tr_regex = re.compile(r'className=\{`border-b border-zinc-900 cursor-pointer \$\{(.*?)\}\`\}', re.DOTALL)
old_action_bar_regex = re.compile(r'className="grid grid-cols-1(.*?)border-b border-zinc-800 bg-zinc-900"')

for fpath in files:
    with open(fpath, 'r') as f:
        content = f.read()

    # 1. Cleanly remove the old header using bracket logic
    content = remove_header(content)

    # 2. String class replacements
    content = content.replace(old_wrapper, new_wrapper)
    content = content.replace(old_input, new_input)
    content = content.replace(old_full_input, new_input)
    content = content.replace(old_btn_blue, new_btn_blue)
    content = content.replace(old_btn_zinc, new_btn_zinc)
    content = content.replace(old_btn_amber, new_btn_amber)
    content = content.replace(old_btn_red, new_btn_red)
    content = content.replace(old_tr_header, new_tr_header)

    # 3. Dynamic Regex replacements using callbacks
    content = old_tr_regex.sub(replace_table_row, content)
    content = old_action_bar_regex.sub(replace_action_bar, content)

    # 4. Containers and search bar styling
    content = content.replace('className="flex-1 overflow-y-auto p-4"', 'className="flex-1 overflow-y-auto p-6 bg-zinc-950 shadow-[inset_0_5px_15px_rgba(0,0,0,0.3)]"')
    content = content.replace('className="flex-1 overflow-y-auto bg-zinc-950 p-4"', 'className="flex-1 overflow-y-auto p-6 bg-zinc-950 shadow-[inset_0_5px_15px_rgba(0,0,0,0.3)]"')

    content = content.replace('<th className="py-2">', '<th className="py-4 px-6">')
    content = content.replace('<td className="py-2">', '<td className="py-4 px-6 font-medium">')

    content = content.replace('className="border-b border-zinc-800 bg-zinc-900 p-4"', 'className="border-b border-zinc-800 bg-zinc-900/50 p-4 mx-4 mb-2 rounded-xl mt-4"')

    with open(fpath, 'w') as f:
        f.write(content)

print(f"Fixed {len(files)} files!")
