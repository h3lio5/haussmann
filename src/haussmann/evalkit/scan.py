"""Turn a text PDF into an image-only PDF that looks scanned."""

# pypdfium2 ships no type information.
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportArgumentType=false

import datetime as dt
import io
import random
import time

import pypdfium2
from PIL import Image, ImageFilter

_DPI = 110
_JPEG_QUALITY = 45
_MAX_TILT_DEGREES = 0.7
_NOISE = 0.08
_BLUR = 0.6


def degrade(pdf: bytes, rng: random.Random, date: dt.date) -> bytes:
    """Same page count, no text layer; identical output for an identical `rng` state."""
    document = pypdfium2.PdfDocument(pdf)
    pages: list[Image.Image] = []
    for index in range(len(document)):
        page = document[index].render(scale=_DPI / 72, grayscale=True).to_pil().convert("L")
        tilt = rng.uniform(-_MAX_TILT_DEGREES, _MAX_TILT_DEGREES)
        page = page.rotate(tilt, resample=Image.Resampling.BICUBIC, fillcolor=255)
        noise = Image.frombytes("L", page.size, rng.randbytes(page.width * page.height))
        pages.append(Image.blend(page, noise, _NOISE).filter(ImageFilter.GaussianBlur(_BLUR)))

    stamp = time.struct_time((date.year, date.month, date.day, 9, 0, 0, 0, 1, 0))
    out = io.BytesIO()
    pages[0].save(
        out,
        "PDF",
        save_all=True,
        append_images=pages[1:],
        resolution=_DPI,
        quality=_JPEG_QUALITY,
        creationDate=stamp,
        modDate=stamp,
    )
    return out.getvalue()
