# Pitfalls

## Images are page scans
99% of images extracted by `extract.py` are full-page scans (1630x2551px).
Real figures require `extract_figures.py` with gap analysis — or better, the
Docling path (`--image-export-mode embedded`), which keeps figures as base64
inline and does not lose the ones embedded in page scans.

## CORS with file://
`fetch()` doesn't work over `file://`. Solution: SPA with all content
embedded in the HTML (no fetch). Build script emits a single ~1.2MB file.

## [^n] in section headings
Footnotes in headings escaped the parser (e.g. `### Debate [^4]`).
Fixed by applying `fix_note_inline()` to headings too, not just paragraphs.

## Divergent slugs between sidebar and headings
Sidebar and headings used different slug logic. With `[^n]` in the title,
one removed it and the other didn't → mismatched anchors.
Solution: unified `make_slug()` used in both places.

## Worker didn't save (stdout vs write_file)
Workers sometimes emit markdown to stdout instead of using write_file.
The prompt MUST explicitly say: "AT THE END, use write_file to SAVE to `{path}`".

## Output with mixed-in reasoning
Prompt must end with "Deliver ONLY the translated markdown. No explanations."
Even so, some flash-tier workers occasionally include reasoning — acceptable;
the build script extracts markdown from the log.

## Nonexistent figures in HTML
Translated markdown references images that were never extracted
(e.g. `fig5_2.png`). `build_site.py` checks `os.path.exists()` before
emitting `<figure>` — missing images are silently ignored.

## Workers addicted to execute_code
Even with "use write_file" explicit, some worker models try `execute_code`
(blocked) instead of `write_file`. For stubborn chapters, the master
translates inline with `read_file` + `write_file` directly, no workers.

## Invisible bold (Forest Floor theme)
`#content strong { color:var(--primary) }` made bold almost equal to text
(#1F3529 vs #2c2c2c). Fixed to `color:var(--tertiary)` (covers #C9733A).

## Context limits
Workers have ~128K tokens of context. Chapters > 40 pages need chunking
(~19 pages per chunk, ~50K chars of input). After translation, merge with `cat`.

## rtk hook in output
First lines of background output contain rtk hook messages. Normal, ignore.

## Event loop closed
Harmless exception at the end of `--cli` sessions. Doesn't affect output.

## Late worker saves
Always run `build_site.py` AFTER all workers finish — workers that save
after the build are not captured.
