import sys
import os

with open("src/renderer/src/Terminal.tsx", "r") as f:
    text = f.read()

# Make sure to import TopNavbar
if "import TopNavbar from './components/TopNavbar'" not in text:
    text = text.replace("import type { ReactElement } from 'react'", "import type { ReactElement } from 'react'\nimport TopNavbar from './components/TopNavbar'")

start_marker = "{/* 1. TOP NAVBAR (Eleventa style) */}"
end_marker = "{/* DEV CONFIG (Collapsible) */}"

start_idx = text.find(start_marker)
end_idx = text.find(end_marker)

if start_idx != -1 and end_idx != -1:
    new_text = text[:start_idx] + "<TopNavbar />\n\n      " + text[end_idx:]
    with open("src/renderer/src/Terminal.tsx", "w") as f:
        f.write(new_text)
    print("Terminal.tsx updated.")
else:
    print("Terminal.tsx markers not found.")

