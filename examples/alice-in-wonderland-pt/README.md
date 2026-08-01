# Demo: Alice no País das Maravilhas (PT-BR)

Full-pipeline demo of `book-to-site`: *Alice's Adventures in Wonderland*
(Lewis Carroll, public domain via Project Gutenberg #11) converted into a
single-file interactive site with all 12 chapters translated to Brazilian
Portuguese.

- Source: Project Gutenberg #11 (public domain)
- PDF: generated with a real TOC (see `make_fixture.py` in this directory)
- Pipeline executed end-to-end by an external coding agent (pi) following
  `SKILL.md` from scratch, without intervention
- Translation: 12 chapters, `deepseek-v4-flash` workers (master-slave contract)
- Output: `index.html` — 185 KB single-file SPA, works offline over `file://`

## Reproduce

```bash
# 1. Download the source text (public domain)
curl -sL "https://www.gutenberg.org/cache/epub/11/pg11.txt" -o pg11.txt
tr -d '\r' < pg11.txt > pg11_n.txt

# 2. Generate a PDF with TOC (fixture script in this directory)
python3 make_fixture.py pg11_n.txt alice.pdf

# 3. Extract + build (no translation — use the English text as-is)
pip install pymupdf Pillow
python3 ../../scripts/extract.py alice.pdf --out-dir output
python3 ../../scripts/build_site.py --chapters-dir output/capitulos \
  --images-dir output/imagens --output index.html \
  --title "Alice in Wonderland" --authors "Lewis Carroll" --lang en

# 4. To reproduce the PT-BR translation, follow SKILL.md → Phase 2
#    (master-slave workers), then rebuild with --lang pt-BR.
```
