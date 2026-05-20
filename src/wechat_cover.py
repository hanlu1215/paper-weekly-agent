"""压缩公众号封面图，避免云托管 JSON 请求体过大导致上传超时。"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

DEFAULT_MAX_SIDE = 900
DEFAULT_JPEG_QUALITY = 82
DEFAULT_MAX_BYTES = 200_000


def compress_cover_image(
    path: Path,
    *,
    max_side: int = DEFAULT_MAX_SIDE,
    quality: int = DEFAULT_JPEG_QUALITY,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> tuple[bytes, str, str]:
    """返回 (jpeg_bytes, filename, content_type)，尽量控制在 max_bytes 以内。"""
    image = Image.open(path)
    if image.mode in ("RGBA", "P"):
        background = Image.new("RGB", image.size, (255, 255, 255))
        if image.mode == "P":
            image = image.convert("RGBA")
        background.paste(image, mask=image.split()[-1] if image.mode == "RGBA" else None)
        image = background
    elif image.mode != "RGB":
        image = image.convert("RGB")

    image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)

    current_quality = quality
    while current_quality >= 50:
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=current_quality, optimize=True)
        data = buffer.getvalue()
        if len(data) <= max_bytes:
            return data, "cover.jpg", "image/jpeg"
        current_quality -= 8

    return data, "cover.jpg", "image/jpeg"
