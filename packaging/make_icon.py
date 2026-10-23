"""assets/logo.png -> assets/app.ico (falls back to a plain placeholder icon)."""
import os
from PIL import Image, ImageDraw

root = os.path.join(os.path.dirname(__file__), "..", "assets")
logo = os.path.join(root, "logo.png")
if os.path.exists(logo):
    im = Image.open(logo).convert("RGBA")
    side = max(im.size)
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.paste(im, ((side - im.width) // 2, (side - im.height) // 2))
else:
    sq = Image.new("RGBA", (256, 256), (11, 58, 91, 255))
    ImageDraw.Draw(sq).rectangle((48, 48, 208, 208), outline="white", width=12)
sq.save(os.path.join(root, "app.ico"), sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
