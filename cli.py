"""Command line: python cli.py input.pptx|.pdf|.png [-o output.pptx]"""
import argparse
import os

from clipsep.core import analyze, load_images
from clipsep.export import export_pptx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--output")
    ap.add_argument("--font", default="Microsoft JhengHei")
    ap.add_argument("--keep-watermark", action="store_true")
    a = ap.parse_args()
    pages = []
    for path in a.inputs:
        for i, img in enumerate(load_images(path), 1):
            print(f"{os.path.basename(path)} #{i}")
            page = analyze(img, drop_watermark=not a.keep_watermark)
            for b in page.blocks:
                b.font = a.font
            pages.append(page)
    out = a.output or os.path.splitext(a.inputs[0])[0] + "_分離.pptx"
    export_pptx(pages, out)
    print("->", out)


if __name__ == "__main__":
    main()
