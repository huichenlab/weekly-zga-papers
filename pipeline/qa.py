from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageChops
from pypdf import PdfReader


def validate_pdf(pdf_path: str | Path, render_root: str | Path = "tmp/qa") -> dict[str, int]:
    pdf = Path(pdf_path)
    if not pdf.exists() or pdf.stat().st_size < 5_000:
        raise ValueError(f"PDF missing or implausibly small: {pdf}")
    reader = PdfReader(str(pdf))
    if not reader.pages:
        raise ValueError("PDF has zero pages")
    for number, page in enumerate(reader.pages, start=1):
        if float(page.mediabox.width) <= float(page.mediabox.height):
            raise ValueError(f"Page {number} is not landscape")
        if len((page.extract_text() or "").strip()) < 35:
            raise ValueError(f"Page {number} has too little extractable text")
    renderer = shutil.which("pdftoppm")
    if not renderer:
        raise RuntimeError("pdftoppm is required for rendered-page QA")
    root = Path(render_root)
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root) as temp_dir:
        prefix = Path(temp_dir) / "page"
        subprocess.run([renderer, "-png", "-r", "120", str(pdf), str(prefix)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        images = sorted(Path(temp_dir).glob("page-*.png"))
        if len(images) != len(reader.pages):
            raise ValueError("Rendered and PDF page counts differ")
        for number, path in enumerate(images, start=1):
            with Image.open(path).convert("RGB") as image:
                white = Image.new("RGB", image.size, "white")
                if ImageChops.difference(image, white).getbbox() is None:
                    raise ValueError(f"Rendered page {number} is blank")
                border = 2
                strips = (image.crop((0, 0, image.width, border)), image.crop((0, image.height - border, image.width, image.height)), image.crop((0, 0, border, image.height)), image.crop((image.width - border, 0, image.width, image.height)))
                if any(ImageChops.difference(strip, Image.new("RGB", strip.size, "white")).getbbox() for strip in strips):
                    raise ValueError(f"Rendered page {number} has content touching an outer edge")
    return {"pages": len(reader.pages), "bytes": pdf.stat().st_size}

