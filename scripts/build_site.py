#!/usr/bin/env python3
"""Build a self-contained single-file SPA from translated markdown chapters.

Reads chapters (prefer *_PT.md, fallback to any *.md), converts to HTML with
footnote tooltips, internal chapter links, figure injection, and emits one
standalone HTML file with all content embedded (no fetch, works over file://).

Usage:
    python3 scripts/build_site.py --chapters-dir chapters --images-dir images \
        --output site/index.html --title "My Book" --authors "Author Name" --lang en
"""

import argparse
import base64
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# Markdown → HTML conversion (validated on real academic books)
# ---------------------------------------------------------------------------

def make_slug(title):
    clean = re.sub(r'\[\^?\d+\]', '', title)
    return re.sub(r'[^a-z0-9]+', '-', clean.lower().strip('-'))


def parse_subsections(text):
    subs = []
    for line in text.split('\n'):
        s = line.strip()
        for level, plen in [(2, 3), (3, 4)]:
            if s.startswith('#' * level + ' '):
                title = re.sub(r'\[\^?\d+\]', '', s[plen:]).strip()
                if not title or re.match(r'^[\*\s]+$', title):
                    break
                subs.append({"level": level, "title": title, "id": make_slug(title)})
                break
    return subs


def apply_inline(s):
    """Apply bold and italic to any string."""
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'\*(.+?)\*', r'<em>\1</em>', s)
    return s


def fix_note_inline(s, notes):
    def rep(m):
        n = m.group(1)
        nt = notes.get(n, '')
        return f'<sup class="fn-ref" data-note="{html.escape(nt)}">[{n}]</sup>' if nt else m.group(0)
    return re.sub(r'\[\^?(\d+)\]', rep, s)


def md_to_html(text, chap_index, images_dir):
    notes = {}
    ns = re.search(r'\n##\s*Notes?\s*(e|&)?\s*References?\s*\n', text)
    if ns:
        for m in re.finditer(r'(?:\[\^?(\d+)\]\s*|(\d+)\.\s+)(.+?)(?=\[\^?\d+\]|\d+\.\s+(?=[A-Z])|\Z)', text[ns.end():], re.DOTALL):
            notes[m.group(1) or m.group(2)] = m.group(3).strip()
        text = text[:ns.start()]

    text = html.escape(text, quote=False)
    # Restore > for blockquote detection (html.escape converts > to &gt;)
    text = text.replace('&gt; ', '> ')
    lines = text.split('\n')
    out = []
    in_table, in_bq = False, False

    for line in lines:
        s = line.strip()
        if s.startswith('!['):
            m = re.match(r'!\[([^\]]*)\]\(([^)]+)\)', s)
            if m:
                alt, src = m.groups()
                if os.path.exists(os.path.join(images_dir, os.path.basename(src))):
                    out.append(f'<figure id="fig-{make_slug(alt)}"><img src="{src}" alt="{alt}" loading="lazy"><figcaption>{alt}</figcaption></figure>')
                continue

        for lvl, tag, plen in [(4, 'h4', 5), (3, 'h3', 4), (2, 'h2', 3)]:
            if s.startswith('#' * lvl + ' '):
                raw = s[plen:]
                out.append(f'<{tag} id="{make_slug(raw)}">{apply_inline(fix_note_inline(raw, notes))}</{tag}>')
                break
        else:
            if s.startswith('# '):
                continue

            s = fix_note_inline(s, notes)

            def link_ch(m):
                cn = int(m.group(1))
                return f'<a href="#" class="internal-link" onclick="event.preventDefault();showChapter({chap_index.get(cn, 0)})">Chapter {cn}</a>' if cn in chap_index else m.group(0)
            s = re.sub(r'Chapter (\d+)', link_ch, s)

            if s.startswith('> '):
                if not in_bq:
                    out.append('<blockquote>')
                    in_bq = True
                out.append(s[2:])
                continue
            elif in_bq and s and not s.startswith('#'):
                out.append('</blockquote>')
                in_bq = False
            elif in_bq:
                out.append('</blockquote>')
                in_bq = False

            if '|' in s and s.count('|') >= 2:
                cells = [c.strip() for c in s.split('|')[1:-1]]
                if all(c.replace('-', '').replace(':', '').replace(' ', '') == '' for c in cells):
                    continue
                if not in_table:
                    out.append('<table>')
                    in_table = True
                is_first = out and out[-1] == '<table>'
                out.append('<tr>' + ''.join(f'<{"th" if is_first else "td"}>{apply_inline(c)}</{"th" if is_first else "td"}>' for c in cells) + '</tr>')
                continue
            elif in_table:
                out.append('</table>')
                in_table = False

            if not s:
                if not in_bq:
                    out.append('')
                continue

            s = apply_inline(s)
            out.append(s)

    if in_bq:
        out.append('</blockquote>')
    if in_table:
        out.append('</table>')

    h = '\n'.join(out)
    h = re.sub(r'\n\n+', '</p><p>', h)
    h = '<p>' + h + '</p>'
    h = h.replace('<p></p>', '')
    for t in ['table', 'blockquote', 'figure']:
        h = h.replace(f'<p><{t}>', f'<{t}>').replace(f'</{t}></p>', f'</{t}>')

    if notes:
        h += '\n<div class="footnotes-section"><hr><h3>Notes</h3>'
        for n in sorted(notes, key=int):
            h += f'<div class="footnote" id="fn-{n}"><span class="fn-num">[{n}]</span> {html.escape(notes[n])}</div>'
        h += '</div>'

    # Post-process: inject figures for "Figure X.Y" references
    def inject_figures(html_text):
        def repl(m):
            raw = m.group(1).rstrip('.')
            fn = raw.replace('.', '_')
            fpath = os.path.join(images_dir, f'fig{fn}.png')
            if os.path.exists(fpath):
                with open(fpath, 'rb') as f:
                    b64 = base64.b64encode(f.read()).decode()
                slug = make_slug(f'Figure {raw}')
                return f'</p><figure id="fig-{slug}"><img src="data:image/png;base64,{b64}" alt="Figure {raw}" loading="lazy"><figcaption>Figure {raw}</figcaption></figure><p><a href="#fig-{slug}" class="internal-link">Figure {raw}</a>'
            return f'<a href="#fig-{make_slug(f"Figure {raw}")}" class="internal-link">Figure {raw}</a>'
        return re.sub(r'Figures?\s+(\d+\.\d+)[a-z.]*', repl, html_text)
    h = inject_figures(h)

    return h


# ---------------------------------------------------------------------------
# Chapter discovery
# ---------------------------------------------------------------------------

def _natural_key(name):
    m = re.match(r'(\d+)', name)
    return (int(m.group(1)), name) if m else (float('inf'), name)


def chapter_title_from_file(path):
    """Use the first `# Heading` as display title, fall back to filename."""
    try:
        with open(path, encoding='utf-8') as f:
            for line in f:
                if line.startswith('# '):
                    return line[2:].strip()
    except OSError:
        pass
    base = os.path.splitext(os.path.basename(path))[0]
    return re.sub(r'^[\d_\-.\s]+', '', base).replace('_', ' ').strip()


def discover_chapters(chapters_dir):
    """Auto-discover chapters: prefer *_PT.md, fallback to any *.md.

    Returns a list of dicts: {"file": str, "title": str}.
    """
    if not os.path.isdir(chapters_dir):
        return []
    names = sorted(os.listdir(chapters_dir))
    mds = [n for n in names if n.endswith('.md')]
    if not mds:
        return []
    pt = [n for n in mds if n.endswith('_PT.md')]
    if pt:
        mds = pt
    else:
        mds = [n for n in mds if n.lower() not in ('readme.md', 'index.md')]
    mds = sorted(mds, key=_natural_key)
    chapters = []
    for n in mds:
        path = os.path.join(chapters_dir, n)
        chapters.append({"file": n, "title": chapter_title_from_file(path)})
    return chapters


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def build(chapters, template_path, out_path, images_dir, book_title=None,
          book_authors=None, book_year=None, lang='en'):
    with open(template_path, encoding='utf-8') as f:
        tpl = f.read()

    # Replace book metadata placeholders
    for ph, val in [('__BOOK_TITLE__', book_title or ''),
                    ('__BOOK_AUTHORS__', book_authors or ''),
                    ('__BOOK_YEAR__', book_year or ''),
                    ('__LANG__', lang)]:
        if val is not None:
            tpl = tpl.replace(ph, val)

    chap_index = {}
    real_idx = 0
    for item in chapters:
        if item.get('file'):
            m = re.match(r'(\d+)', item.get('title') or '')
            if m:
                chap_index[int(m.group(1))] = real_idx
            real_idx += 1

    data = []
    for item in chapters:
        if not item.get('file'):
            data.append({"type": "part", "title": item.get('title', ''),
                         "html": "", "subsections": [], "readTime": ""})
            continue
        path = os.path.join(chapters_dir, item['file'])
        if not os.path.exists(path):
            continue
        with open(path, encoding='utf-8') as f:
            content = f.read()
        subs = parse_subsections(content)
        h = md_to_html(content, chap_index, images_dir)
        if subs:
            toc = '<div class="mini-toc"><strong>In this chapter:</strong><ul>'
            for s in subs:
                toc += f'<li class="mt-{s["level"]}"><a href="#{s["id"]}">{html.escape(s["title"])}</a></li>'
            toc += '</ul></div>'
            h = h.replace('</p>', '</p>' + toc, 1)
        words = len(content.split())
        data.append({"type": "chapter", "title": item['title'], "html": h,
                     "subsections": subs, "readTime": f"{max(1, words // 200)} min"})

    js = json.dumps(data, ensure_ascii=False)
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(tpl.replace('__BOOK_DATA__', js))

    size = os.path.getsize(out_path) / (1024 * 1024)
    n = sum(1 for d in data if d['type'] == 'chapter')
    print(f"OK {out_path}  ({size:.1f} MB, {n} chapters)")


def load_chapters_json(path):
    """Explicit chapter list for custom ordering / part dividers.

    JSON shape: [{"file": "01_intro.md", "title": "Introduction"},
                 {"file": null, "title": "Part II"}, ...]
    """
    with open(path, encoding='utf-8') as f:
        items = json.load(f)
    return [{"file": it.get("file"), "title": it.get("title", "")} for it in items]


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--chapters-dir', default='chapters',
                   help='Directory with translated markdown chapters (default: chapters)')
    p.add_argument('--images-dir', default='images',
                   help='Directory with figure images (default: images)')
    p.add_argument('--output', default='site/index.html',
                   help='Output HTML path (default: site/index.html)')
    p.add_argument('--template',
                   default=os.path.join(HERE, '..', 'templates', 'site.html'),
                   help='HTML template with __BOOK_DATA__ placeholder')
    p.add_argument('--chapters-json',
                   help='Optional explicit chapter list JSON (custom order / part dividers)')
    p.add_argument('--title', help='Book title (fills __BOOK_TITLE__)')
    p.add_argument('--authors', help='Book authors (fills __BOOK_AUTHORS__)')
    p.add_argument('--year', help='Book year (fills __BOOK_YEAR__)')
    p.add_argument('--lang', default='en', help='HTML lang attribute (default: en)')
    return p.parse_args(argv)


def main(argv=None):
    global chapters_dir
    args = parse_args(argv)
    chapters_dir = args.chapters_dir
    if args.chapters_json:
        chapters = load_chapters_json(args.chapters_json)
    else:
        chapters = discover_chapters(args.chapters_dir)
    if not chapters:
        print(f"error: no markdown chapters found in {args.chapters_dir!r} "
              f"(looked for *_PT.md or *.md)", file=sys.stderr)
        return 1
    build(chapters, args.template, args.output, args.images_dir,
          book_title=args.title, book_authors=args.authors, book_year=args.year,
          lang=args.lang)
    return 0


if __name__ == '__main__':
    sys.exit(main())
