#!/usr/bin/env python3
"""Extract real figures from a PDF by detecting gaps between text blocks.

Full-page scans (1630x2551px) are discarded; only regions between text
blocks that look like figure captions ("Figure X.Y ...") are cropped out.
Writes figures_index.json alongside the images.

Usage:
    python3 scripts/extract_figures.py book.pdf --out-dir output/imagens
"""

import argparse
import json
import os
import re
import sys

import fitz  # pymupdf
from PIL import Image


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('pdf', help='Path to the PDF book')
    p.add_argument('--out-dir', default='output/imagens',
                   help='Output directory for figures (default: output/imagens)')
    p.add_argument('--gap-threshold', type=float, default=60.0,
                   help='Minimum vertical gap (pt) to consider a figure region (default: 60)')
    p.add_argument('--dpi', type=int, default=200,
                   help='Render DPI for cropping (default: 200)')
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    pdf_path = args.pdf
    out_dir = args.out_dir

    if not os.path.exists(pdf_path):
        print(f"error: PDF not found: {pdf_path}", file=sys.stderr)
        return 1

    doc = fitz.open(pdf_path)
    figures = []

    for pnum in range(doc.page_count):
        page = doc[pnum]
        blocks = page.get_text("blocks")
        if not blocks:
            continue

        blocks_sorted = sorted(blocks, key=lambda b: b[1])
        prev_bottom = 0

        for b in blocks_sorted:
            x0, y0, x1, y1, text, _, _ = b
            gap = y0 - prev_bottom

            if gap > args.gap_threshold:
                fig_match = re.match(r'Figure\s+([\d.]+)\s+(.+)', text.strip())
                if fig_match:
                    fig_num = fig_match.group(1)
                    fig_title = fig_match.group(2)[:100]

                    pix = page.get_pixmap(dpi=args.dpi)
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    scale = pix.width / page.rect.width

                    margin = 40
                    left = int(margin * scale)
                    right = int((page.rect.width - margin) * scale)
                    top_px = int(prev_bottom * scale)
                    bottom_px = int((y0 - 5) * scale)

                    if bottom_px > top_px + 50:
                        fig_img = img.crop((left, top_px, right, bottom_px))
                        fname = f"fig{fig_num.replace('.', '_')}.png"
                        fpath = os.path.join(out_dir, fname)
                        os.makedirs(out_dir, exist_ok=True)
                        fig_img.save(fpath)

                        figures.append({
                            "number": fig_num, "title": fig_title,
                            "page": pnum + 1, "file": fname,
                            "size": list(fig_img.size),
                        })
                        print(f"  Figure {fig_num}: {fname} — p{pnum + 1}")

            if y1 > prev_bottom:
                prev_bottom = y1

    doc.close()

    index_path = os.path.join(out_dir, "figures_index.json")
    with open(index_path, 'w') as f:
        json.dump({"total": len(figures), "figures": figures}, f, indent=2,
                  ensure_ascii=False)

    print(f"\nOK {len(figures)} figures -> {index_path}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
