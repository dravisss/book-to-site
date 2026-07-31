---
name: book-to-site
description: "Use when turning a PDF book into a self-contained interactive website. Extracts text and figures (pymupdf, optional Docling for scans), translates via cheap LLM workers (master-slave), and builds a single-file SPA with navigation, footnote tooltips, search, and a configurable design system."
version: 1.0.0
author: Ravi Resck
license: MIT
platforms: [macos, linux]
metadata:
  hermes:
    tags: [pdf, translation, site-generator, master-slave, book]
---

# Book-to-Site Pipeline

Turns a PDF book into a self-contained interactive website: extracts text and
figures, translates the full text via cheap LLM workers (master-slave), and
builds a single-file SPA with sidebar navigation, footnote tooltips, full-text
search, and a customizable design system. It does NOT summarize — it translates
in full.

## When to Use

- "Turn this book into an interactive website"
- "Extract a PDF, translate it, and generate a site"
- "Create a web version of an academic book"

Don't use for: single documents or articles (use a regular HTML conversion),
or when the user wants a summary (this pipeline translates everything).

## Prerequisites

```bash
pip install pymupdf Pillow        # required (extraction + figures)
```

Optional, per phase:
- Translation (master-slave): a `hermes` CLI in PATH and any configured
  provider/model. The stack is provider-agnostic — see Worker Contract.
- Scanned PDFs: `docling` CLI (advanced extractor, see Docling section).
  Falls back to pymupdf text extraction + LLM re-write.

## Architecture

```
PDF → extract.py (pymupdf) → chapters/ NNN_title.md + images/
                ↓ (optional) extract_figures.py → real figures via gap analysis
       LLM workers (cheap model) → translated chapters *_PT.md
                ↓
       build_site.py → self-contained single-file SPA (works over file://)
```

## Quick Start

```bash
# 1. Inspect
python3 -c "import fitz; d=fitz.open('book.pdf'); print(d.page_count); [print(f'  {l} {t} p{p}') for l,t,p in d.get_toc()[:20]]"

# 2. Extract text + figures
python3 scripts/extract.py book.pdf --out-dir output
python3 scripts/extract_figures.py book.pdf --out-dir output/imagens

# 3. Translate chapters (master-slave, see Worker Contract) → output/capitulos/*_PT.md

# 4. Build the site
python3 scripts/build_site.py --chapters-dir output/capitulos \
  --images-dir output/imagens --output site/index.html \
  --title "My Book" --authors "Author Name" --lang en

# 5. Open
open site/index.html
```

## Pipeline

### Phase 0: Inspect

Use `fitz.open()` to read page count and TOC — this tells you how to split
chapters and estimate worker chunking.

### Phase 1: Extract

**`scripts/extract.py`** (pymupdf, default): extracts text per page, saves all
embedded images, maps chapters from the PDF outline, writes one markdown file
per chapter (`NNN_title.md`) plus `index.json`.

**`scripts/extract_figures.py`**: full-page scans (1630x2551px) are useless as
figures. This script detects vertical gaps between text blocks and crops
regions above "Figure X.Y" captions. Writes `figures_index.json`.

> Note: chapter files use the `NNN_title.md` naming so the build script can
> auto-discover and order them.

### Phase 2: Translate (Master-Slave)

The master agent prepares prompts and fires background `hermes chat` workers
with a cheap model. Workers receive raw text + rules, translate, and save via
`write_file`. See [Worker Contract](#worker-contract) and
`references/translate-prompt.md` for prompt evolution history.

Patterns:

1. **One-shot**: chapters < 20 pages. One worker, translate directly.
2. **Parallel chunking**: chapters > 40 pages. Split into ~19-page chunks,
   N workers in parallel (batches of 3), merge with `cat`.
3. **write_file**: always instruct the worker to save via `write_file` at the
   end — stdout output gets lost.
4. **Merge**: `cat parte1.md parte2.md > capitulo.md`

Monitoring: launch with `terminal(background=True)`, poll with
`process(action='poll'|'wait'|'log')`.

### Phase 3: Build

```bash
python3 scripts/build_site.py --chapters-dir chapters --images-dir images \
  --output site/index.html --title "Title" --authors "Author" --lang en
```

The script:
1. Auto-discovers chapters: prefers `*_PT.md`, falls back to any `*.md`
   (ordered by numeric prefix). For custom ordering or part dividers, pass
   `--chapters-json` (see `load_chapters_json` in the script).
2. Converts Markdown → HTML: `[^n]` footnotes become tooltips with real
   content, "Chapter N" links become internal navigation, "Figure X.Y"
   references inject the actual image (base64, works offline).
3. Generates a single-file SPA with all chapters embedded (no fetch — works
   over `file://`).
4. Applies the template design system (default: Forest Floor —
   Cormorant Garamond + Inter, light/dark/sepia).

## Worker Contract

Workers run `hermes chat` in background with a cheap model chosen per call.
The stack is fully configurable via environment variables:

```bash
export WORKER_MODEL="${WORKER_MODEL:-deepseek-v4-flash}"   # any cheap fast model
export WORKER_PROVIDER="${WORKER_PROVIDER:-}"              # your provider, e.g. opencode-go
export WORKER_MAX_TURNS="${WORKER_MAX_TURNS:-4}"           # 4-5 for large chunks

hermes chat -m "$WORKER_MODEL" --provider "$WORKER_PROVIDER" \
  --quiet --max-turns "$WORKER_MAX_TURNS" --cli \
  -q "$(cat /tmp/prompt.txt)"
```

Why `hermes chat` background instead of `delegate_task`:

| | delegate_task | hermes chat background |
|---|---|---|
| Model per call | ❌ global config only | ✅ `-m` + `--provider` |
| Monitoring | transcript file | `process('poll')` live stdout |
| Cost | inherits master model | cheap model per worker |
| Persistence | ephemeral subagent | session saved, resumable |

Critical flags:
- `--quiet`: suppress banner/spinner (script mode)
- `--max-turns N`: 3-4 for chapters, 4-5 for large chunks
- `--cli`: avoid interactive TUI

## Translation Prompt

Canonical v3 prompt (see `references/translate-prompt.md` for evolution):

```
You are an academic translator and editor. Transform the raw text below into
clean **{target_language} academic Markdown**.

RULES:
1. TRANSLATE EVERYTHING faithfully. Do not summarize, do not omit.
2. FIX layout breaks and split paragraphs.
3. HEADINGS: use ## and ### where the topic changes; # for the title.
4. CITATIONS: preserve references (Author, year). *italics* for foreign terms.
5. REMOVE page markers and repeated running headers. Text must flow continuously.
6. NATURAL paragraphs, 3-8 sentences, no artificial breaks.
7. FIGURES: [dynamic: list chapter figures from figures_index.json if any,
   else "Do NOT include images"]
8. AT THE END, use the write_file tool to SAVE the markdown to: {path}

Deliver ONLY the translated markdown. No explanations.
```

Example for Portuguese: `{target_language}` = `português brasileiro acadêmico`.

## Docling (optional, for scanned PDFs)

For scanned PDFs where pymupdf text is unusable:

```bash
docling "book.pdf" --to md --output . --image-export-mode embedded
```

Docling (IBM) produces a single large markdown with base64 images inline.
Then: extract figures from the markdown (find "Figure X.Y" caption before each
`data:image`), split into chapters manually using the book TOC (never by `## `
headings — subsections explode into hundreds of fragments), and proceed with
translation.

**Pitfall**: Docling depends on `av`/`cv2` — if it crashes with a libavdevice
conflict, `pip uninstall av` or use a clean venv. Fallback: pymupdf text +
LLM workers rewriting the OCR (same pipeline, workers fix the noise).

## Customizing the Design System

The template (`templates/site.html`) is a plain HTML file with placeholders
`__BOOK_TITLE__`, `__BOOK_AUTHORS__`, `__BOOK_YEAR__`, `__LANG__`,
`__BOOK_DATA__`. All CSS variables live in `:root` — recolor the site by
editing the variables or swap the whole file.

## Pitfalls

- **Full-page scans as "figures"**: 99% of embedded images in scanned PDFs are
  page scans. Use `extract_figures.py` (gap analysis) — never include page
  scans as figures.
- **CORS with file://**: `fetch()` doesn't work over `file://`. The build
  script embeds everything (content + base64 images) in one HTML — no fetch.
- **`[^n]` in headings**: footnote refs in headings escape naive parsers.
  `fix_note_inline()` is applied to headings too, and `make_slug()` is unified
  between sidebar and headings (divergent slug logic broke anchors).
- **Worker didn't save**: workers sometimes emit markdown to stdout instead of
  calling write_file. The prompt MUST say "AT THE END, use write_file to SAVE
  the markdown to: {path}". Then "Deliver ONLY the translated markdown."
- **Missing figure files**: translated markdown may reference figures that
  weren't extracted. The build script checks `os.path.exists()` and silently
  skips missing ones — no broken `<figure>` tags.
- **execute_code addiction**: some worker models try `execute_code` instead of
  `write_file`. Explicitly instruct write_file; for stubborn chapters the
  master translates inline with `read_file` + `write_file`.
- **Context limits**: workers have ~128K tokens. Chapters > 40 pages need
  chunking (~19 pages/chunk, ~50K chars input). Merge with `cat` after.
- **Large PDFs**: 500+ page books produce 7-15MB Docling markdown — normal.
  Docling on 596 pages can take 10+ min. Patience.
- **Chapter splitting**: NEVER auto-split by `## ` headings (subsections
  explode into 100+ "chapters"). Always map real chapter boundaries from the
  book TOC.
- **rtk hook / event-loop noise**: rtk hook lines at the start of background
  output and "Event loop is closed" at the end are harmless.
- **Rebuild after workers**: always run `build_site.py` AFTER all workers
  finish — late saves are not picked up by an earlier build.

## Verification

```bash
# All chapters translated?
ls chapters/*_PT.md | wc -l

# Build succeeded and site opens
open site/index.html

# Manual check: click "Chapter 1" in the text → navigates; hover [1] → tooltip
# with real footnote; figures referenced inline as base64 (works offline).
```

## Quick Reference

| Tool | Purpose |
|---|---|
| `scripts/extract.py book.pdf --out-dir output` | PDF → chapters/ + images/ + index.json |
| `scripts/extract_figures.py book.pdf --out-dir output/imagens` | Real figures via gap analysis |
| `hermes chat -m "$WORKER_MODEL" ...` | Translation worker (master-slave) |
| `scripts/build_site.py --chapters-dir ...` | MDs → single-file SPA |
| `templates/site.html` | SPA template with `__BOOK_DATA__` |
