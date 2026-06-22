from __future__ import annotations

from typing import Any


DEFAULT_RESPONSIVE_CONFIG: dict[str, dict[str, int]] = {
    "mobile": {
        "maxWidth": 767,
        "previewWidth": 375,
        "previewHeight": 667,
    },
    "tablet": {
        "minWidth": 768,
        "maxWidth": 1119,
        "previewWidth": 768,
        "previewHeight": 1024,
    },
    "desktop": {
        "minWidth": 1120,
        "previewWidth": 1120,
        "previewHeight": 768,
    },
}

LEGACY_DESKTOP_PREVIEW_WIDTH = 1024
LEGACY_DESKTOP_MIN_WIDTH = 1024


def _coerce_int(raw: Any, default: int, min_value: int, max_value: int) -> int:
    try:
        value = int(raw)
    except Exception:
        value = default
    return max(min_value, min(max_value, value))


def _desktop_preview_width_source(raw: Any) -> Any:
    try:
        if int(raw) == LEGACY_DESKTOP_PREVIEW_WIDTH:
            return DEFAULT_RESPONSIVE_CONFIG["desktop"]["previewWidth"]
    except Exception:
        pass
    return raw


def _desktop_min_width_source(raw: Any) -> Any:
    try:
        if int(raw) == LEGACY_DESKTOP_MIN_WIDTH:
            return DEFAULT_RESPONSIVE_CONFIG["desktop"]["minWidth"]
    except Exception:
        pass
    return raw


def normalize_responsive_config(raw: Any) -> dict[str, dict[str, int]]:
    source = raw if isinstance(raw, dict) else {}
    defaults = DEFAULT_RESPONSIVE_CONFIG

    mobile_raw = source.get("mobile") if isinstance(source.get("mobile"), dict) else {}
    desktop_raw = source.get("desktop") if isinstance(source.get("desktop"), dict) else {}

    mobile_max = _coerce_int(
        mobile_raw.get("maxWidth"),
        defaults["mobile"]["maxWidth"],
        240,
        4094,
    )
    desktop_min = _coerce_int(
        _desktop_min_width_source(desktop_raw.get("minWidth")),
        max(defaults["desktop"]["minWidth"], mobile_max + 2),
        mobile_max + 2,
        4096,
    )
    tablet_min = mobile_max + 1
    tablet_max = desktop_min - 1
    tablet_raw = source.get("tablet") if isinstance(source.get("tablet"), dict) else {}

    return {
        "mobile": {
            "maxWidth": mobile_max,
            "previewWidth": _coerce_int(
                mobile_raw.get("previewWidth"),
                defaults["mobile"]["previewWidth"],
                64,
                4096,
            ),
            "previewHeight": _coerce_int(
                mobile_raw.get("previewHeight"),
                defaults["mobile"]["previewHeight"],
                64,
                8192,
            ),
        },
        "tablet": {
            "minWidth": tablet_min,
            "maxWidth": tablet_max,
            "previewWidth": _coerce_int(
                tablet_raw.get("previewWidth"),
                defaults["tablet"]["previewWidth"],
                64,
                4096,
            ),
            "previewHeight": _coerce_int(
                tablet_raw.get("previewHeight"),
                defaults["tablet"]["previewHeight"],
                64,
                8192,
            ),
        },
        "desktop": {
            "minWidth": desktop_min,
            "previewWidth": _coerce_int(
                _desktop_preview_width_source(desktop_raw.get("previewWidth")),
                defaults["desktop"]["previewWidth"],
                64,
                4096,
            ),
            "previewHeight": _coerce_int(
                desktop_raw.get("previewHeight"),
                defaults["desktop"]["previewHeight"],
                64,
                8192,
            ),
        },
    }


def responsive_media_query(media_scope: str | None, responsive: Any) -> str:
    cfg = normalize_responsive_config(responsive)
    if media_scope == "tablet":
        return (
            f"(min-width: {cfg['tablet']['minWidth']}px) "
            f"and (max-width: {cfg['tablet']['maxWidth']}px)"
        )
    if media_scope == "mobile":
        return f"(max-width: {cfg['mobile']['maxWidth']}px)"
    if media_scope == "desktop":
        return f"(min-width: {cfg['desktop']['minWidth']}px)"
    return ""


def responsive_preview_widths(responsive: Any) -> dict[str, int]:
    cfg = normalize_responsive_config(responsive)
    return {
        "mobile": cfg["mobile"]["previewWidth"],
        "tablet": cfg["tablet"]["previewWidth"],
        "desktop": cfg["desktop"]["previewWidth"],
    }
