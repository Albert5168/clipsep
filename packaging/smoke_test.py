"""Fails the build if OCR or export breaks: render known text, read it back, export a pptx."""
import os, sys, tempfile
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from clipsep.core import analyze
from clipsep.export import export_pptx

font = ImageFont.truetype("msjh.ttc" if os.name == "nt" else "DejaVuSans.ttf", 48)
im = Image.new("RGB", (1376, 768), "white")
ImageDraw.Draw(im).text((100, 100), "水產養殖 Aquaculture 2026", font=font, fill=(10, 30, 60))
page = analyze(np.array(im)[:, :, ::-1].copy())
text = " ".join(b.text for b in page.blocks)
print("OCR:", text)
assert "Aquaculture" in text, text
out = os.path.join(tempfile.mkdtemp(), "t.pptx")
export_pptx([page], out)
assert os.path.getsize(out) > 0
print("ok")
