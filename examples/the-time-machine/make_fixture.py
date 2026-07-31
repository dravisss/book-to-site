#!/usr/bin/env python3
"""Generate a test PDF from The Time Machine (Project Gutenberg #35).

Creates a page-per-block PDF with a real TOC so extract.py can map chapters.
Body chapters are marked by roman-numeral lines ("I.", "II.", ...) + "Epilogue".
"""
import re, sys
import fitz

SRC = sys.argv[1] if len(sys.argv) > 1 else "pg35.txt"  # CRLF-normalized
OUT = sys.argv[2] if len(sys.argv) > 2 else "time_machine.pdf"

text = open(SRC, encoding="utf-8", errors="replace").read()

# Body starts at the first "I." marker after the table of contents
start = text.find("\n I.\n")
body = text[start:]

# Split into chapters by roman numeral + "." or "Epilogue" (lines may be indented)
pat = re.compile(r"^[ ]*(X{0,3}(IX|IV|V?I{0,3}))\.$|^[ ]*Epilogue$", re.MULTILINE)
matches = list(pat.finditer(body))
chapters = []
for i, m in enumerate(matches):
    numeral = m.group(1) or "Epilogue"
    content = body[m.end():matches[i + 1].start() if i + 1 < len(matches) else len(body)]
    content = re.sub(r"\n{3,}", "\n\n", content).strip()
    chapters.append((numeral, content))

print(f"{len(chapters)} chapters parsed")

doc = fitz.open()
toc = []
for numeral, content in chapters:
    title = f"Chapter {numeral}"
    lines = content.split("\n")
    first_page = len(doc) + 1
    for i in range(0, len(lines), 45):
        page = doc.new_page()
        chunk = "\n".join(lines[i:i + 45])
        page.insert_text((50, 60), chunk, fontsize=8, fontname="helv")
    toc.append([1, title, first_page])

doc.set_toc(toc)
doc.save(OUT)
print(f"OK {OUT} — {doc.page_count} pages, {len(toc)} TOC entries")
