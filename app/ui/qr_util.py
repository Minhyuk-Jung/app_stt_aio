"""QR pixmap helper for remote pairing (C15)."""

from __future__ import annotations


def make_qr_pixmap(data: str, *, size: int = 180):
    """Return QPixmap for URL/PIN QR, or None when qrcode is unavailable."""
    if not data.strip():
        return None
    try:
        import qrcode
        from PySide6.QtGui import QImage, QPixmap
    except ImportError:
        return None

    qr = qrcode.QRCode(box_size=4, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    width, height = image.size
    buffer = image.tobytes("raw", "RGB")
    qimage = QImage(buffer, width, height, width * 3, QImage.Format.Format_RGB888)
    pixmap = QPixmap.fromImage(qimage)
    return pixmap.scaled(size, size)
