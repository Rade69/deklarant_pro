from dataclasses import dataclass
from hashlib import sha1


@dataclass(frozen=True)
class DisplayProfile:
    name: str
    width_ratio: float
    height_ratio: float
    maximize_by_default: bool
    tab_icon_size: int


COMPACT = DisplayProfile("compact", 1.0, 1.0, True, 20)
STANDARD = DisplayProfile("standard", 0.96, 0.94, True, 22)
LARGE = DisplayProfile("large", 0.90, 0.90, False, 24)


def classify_display(width: int, height: int) -> DisplayProfile:
    if width <= 1600 or height <= 850:
        return COMPACT
    if width <= 2560 and height <= 1440:
        return STANDARD
    return LARGE


def build_display_key(
    name: str,
    width: int,
    height: int,
    device_pixel_ratio: float,
    manufacturer: str = "",
    model: str = "",
    serial_number: str = "",
) -> str:
    identity = "|".join(
        (
            name.strip(),
            manufacturer.strip(),
            model.strip(),
            serial_number.strip(),
            f"{width}x{height}",
            f"{device_pixel_ratio:.2f}",
        )
    )
    return sha1(identity.encode("utf-8")).hexdigest()[:16]


def display_key_for_screen(screen) -> str:
    available = screen.availableGeometry()
    return build_display_key(
        screen.name() or "display",
        available.width(),
        available.height(),
        float(screen.devicePixelRatio()),
        screen.manufacturer() or "",
        screen.model() or "",
        screen.serialNumber() or "",
    )


def profile_for_screen(screen) -> DisplayProfile:
    available = screen.availableGeometry()
    return classify_display(available.width(), available.height())
