#!/usr/bin/env python3
"""Extract text from a PDF book, organized by chapter using the TOC.

Extracts per-page images, maps chapters via the PDF outline, and writes one
markdown file per chapter plus an index.json.

Usage:
    python3 scripts/extract.py book.pdf --out-dir output
"""

import argparse
import json
import os
import sys
from pathlib import Path

import fitz  # pymupdf


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('pdf', help='Path to the PDF book')
    p.add_argument('--out-dir', default='output',
                   help='Output directory (default: output)')
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    pdf_path = args.pdf
    out = Path(args.out_dir)

    if not os.path.exists(pdf_path):
        print(f"error: PDF not found: {pdf_path}", file=sys.stderr)
        return 1

    doc = fitz.open(pdf_path)
    print(f"Book: {doc.metadata.get('title') or pdf_path} — {doc.page_count} pages")

    # Extract images
    img_dir = out / "imagens"
    img_dir.mkdir(parents=True, exist_ok=True)

    img_map = {}
    for i in range(doc.page_count):
        imgs = doc[i].get_images()
        page_imgs = []
        for j, img in enumerate(imgs):
            xref = img[0]
            base = doc.extract_image(xref)
            ext = base["ext"]
            fname = f"p{i + 1:03d}_{j + 1:02d}.{ext}"
            (img_dir / fname).write_bytes(base["image"])
            page_imgs.append(fname)
        if page_imgs:
            img_map[i] = page_imgs

    print(f"Images extracted: {sum(len(v) for v in img_map.values())}")

    # Map chapters from TOC
    toc = doc.get_toc()
    chapters = []
    for level, title, page in toc:
        chapters.append({"level": level, "title": title.strip(),
                         "start_page": page - 1})

    for i, ch in enumerate(chapters):
        ch["end_page"] = (chapters[i + 1]["start_page"] - 1
                          if i < len(chapters) - 1 else doc.page_count - 1)

    # Extract text per chapter
    cap_dir = out / "capitulos"
    cap_dir.mkdir(parents=True, exist_ok=True)

    chapter_files = []
    for idx, ch in enumerate(chapters):
        start, end = ch["start_page"], ch["end_page"]
        safe_title = ch["title"].replace("/", "-").replace(":", " -")[:80]
        fname = f"{idx + 1:02d}_{safe_title}.md"
        fpath = cap_dir / fname

        lines = [f"# {ch['title']}\n",
                 f"> Pages {start + 1}–{end + 1} | {end - start + 1} pages\n"]

        for pnum in range(start, end + 1):
            page = doc[pnum]
            text = page.get_text("text")
            if text.strip():
                lines.append(f"<!-- p{pnum + 1} -->\n")
                lines.append(text)
                lines.append("")
            if pnum in img_map:
                for imgf in img_map[pnum]:
                    lines.append(f"\n![Figure](imagens/{imgf})\n")

        fpath.write_text("\n".join(lines))
        chapter_files.append({
            "num": idx + 1, "title": ch["title"],
            "file": str(fpath.relative_to(out)),
            "pages": f"{start + 1}–{end + 1}",
            "page_count": end - start + 1,
        })
        print(f"  {fname} ({end - start + 1}p)")

    index = {
        "book": doc.metadata.get("title", "Unknown"),
        "total_pages": doc.page_count,
        "total_images": sum(len(v) for v in img_map.values()),
        "chapters": chapter_files,
    }
    (out / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False))
    print(f"\nOK {len(chapter_files)} chapters in {cap_dir}")
    doc.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
