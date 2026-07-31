# Translation Prompt: Evolution

## v1
Verbose initial prompt. Asked to preserve images as `![Figure](imagens/pXXX...)`,
included a page-marker rule (`> — page NN —`).

**Problems:**
- Page scans inserted into the text
- Page markers polluted reading
- Output with mixed-in reasoning

## v2
Removed the image instruction. Markers changed to "REMOVE, do NOT recreate
numbering".

**Fixed:** page scans removed.
**New problem:** markers still appeared in some cases.

## v3 — Canonical (used from chapter 3 onwards)
Tight prompt, numbered rules, write_file instruction:

```
You are an academic translator and editor. Transform the raw text below into
clean **{target_language} academic Markdown**.

RULES:
1. TRANSLATE EVERYTHING faithfully. Do not summarize.
2. FIX layout breaks and split paragraphs.
3. HEADINGS: use ## and ### where the topic changes.
4. CITATIONS: preserve references (Author, year). *italics* for foreign terms.
5. REMOVE page markers and repeated running headers.
6. NATURAL paragraphs, 3-8 sentences.
7. FIGURES: [dynamic: list chapter figures if any, else "Do NOT include images"]
8. AT THE END, use write_file to SAVE to: `{path}`

Deliver ONLY the translated markdown. No explanations.
```

**Why it works:**
- Short, direct rules (1 line each)
- No ambiguous instructions
- Explicit write_file avoids output loss
- Dynamic figure section (read from `figures_index.json`)
