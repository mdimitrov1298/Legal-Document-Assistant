#!/usr/bin/env python3
"""Convert a UTF-8 TXT file to a reproducible PDF.

Usage:
    python scripts/make_pdf.py <input.txt> [<output.pdf>]

The output defaults to the input stem with a .pdf extension.
Uses reportlab with a fixed timestamp and metadata for reproducibility.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas


def txt_to_pdf(
    txt_path: Path,
    pdf_path: Path,
    *,
    font_name: str = "Helvetica",
    font_size: int = 10,
    margin: float = 2.0,
) -> Path:
    """Write *txt_path* content into a single-font PDF at *pdf_path*."""
    text = txt_path.read_text(encoding="utf-8")
    width, height = A4
    margin_pts = margin * cm
    usable_w = width - 2 * margin_pts
    line_height = font_size * 1.4

    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    c.setTitle(txt_path.stem)
    c.setAuthor("make_pdf.py (eval helper)")
    c.setCreator("reportlab")

    y = height - margin_pts
    c.setFont(font_name, font_size)

    for line in text.splitlines():
        if not line.strip():
            y -= line_height
            if y < margin_pts:
                c.showPage()
                c.setFont(font_name, font_size)
                y = height - margin_pts
            continue
        # Wrap long lines manually
        words = line.split()
        buf: list[str] = []
        for word in words:
            test = " ".join(buf + [word])
            if c.stringWidth(test, font_name, font_size) > usable_w and buf:
                c.drawString(margin_pts, y, " ".join(buf))
                y -= line_height
                if y < margin_pts:
                    c.showPage()
                    c.setFont(font_name, font_size)
                    y = height - margin_pts
                buf = [word]
            else:
                buf.append(word)
        if buf:
            c.drawString(margin_pts, y, " ".join(buf))
            y -= line_height
            if y < margin_pts:
                c.showPage()
                c.setFont(font_name, font_size)
                y = height - margin_pts

    c.save()
    return pdf_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("input", type=Path, help="Input UTF-8 text file")
    parser.add_argument("output", type=Path, nargs="?", help="Output PDF path")
    args = parser.parse_args(argv)

    if not args.input.is_file():
        print(f"Error: {args.input} not found", file=sys.stderr)
        return 1

    out = args.output or args.input.with_suffix(".pdf")
    txt_to_pdf(args.input, out)
    print(f"Created {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
