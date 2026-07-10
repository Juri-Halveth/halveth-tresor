"""Generate assets/icon.ico (a padlock on a dark gradient) for the app and the shortcut."""

import os

from PIL import Image, ImageDraw

S = 256
top, bot = (34, 47, 82), (11, 16, 30)
acc = (126, 168, 255, 255)
hole = (12, 17, 30, 255)

grad = Image.new("RGBA", (S, S))
gd = ImageDraw.Draw(grad)
for y in range(S):
    t = y / (S - 1)
    gd.line(
        [(0, y), (S, y)],
        fill=(
            int(top[0] * (1 - t) + bot[0] * t),
            int(top[1] * (1 - t) + bot[1] * t),
            int(top[2] * (1 - t) + bot[2] * t),
            255,
        ),
    )

mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=58, fill=255)
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
img.paste(grad, (0, 0), mask)

d = ImageDraw.Draw(img)
d.rounded_rectangle([2, 2, S - 3, S - 3], radius=56, outline=(96, 142, 255, 110), width=3)
cx = 128
d.arc([cx - 44, 56, cx + 44, 150], start=180, end=360, fill=acc, width=17)  # shackle
d.rounded_rectangle([cx - 58, 116, cx + 58, 198], radius=22, fill=acc)  # body
d.ellipse([cx - 13, 140, cx + 13, 166], fill=hole)  # keyhole
d.polygon([(cx - 6, 160), (cx + 6, 160), (cx + 9, 186), (cx - 9, 186)], fill=hole)

OUT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets", "icon.ico"))
img.save(OUT, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("wrote", OUT)
