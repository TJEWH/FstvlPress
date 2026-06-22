from __future__ import annotations

from datetime import datetime, timezone
import ipaddress
import re
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4
from xml.sax.saxutils import escape

from app.collection_names import (
    DESIGN_CONFIG_COLLECTION,
    PAGE_REDIRECTS_COLLECTION,
    PAGES_COLLECTION,
    SITEMAP_CONFIG_COLLECTION,
)
from app.media_responsive import (
    collect_raster_image_urls_from_payload,
    enrich_raster_payload_with_asset_docs,
    fetch_asset_docs_by_urls,
)

REDIRECTS_COLLECTION = PAGE_REDIRECTS_COLLECTION
ADMIN_SITEMAP_CONFIG_KEY = SITEMAP_CONFIG_COLLECTION
LEGACY_DESIGN_SETTINGS_KEY = "global"
ALLOWED_EXTERNAL_NAV_ICONS = {
    "other",
    "facebook",
    "instagram",
    "twitter",
    "youtube",
    "tiktok",
}
ALLOWED_REDIRECT_STATUS_CODES = {301, 302, 307, 308, 410}
REDIRECT_ANONYMOUS_HIT_COUNT_FIELD = "anonymous_hit_count"
REDIRECT_LAST_TRIGGERED_AT_FIELD = "last_triggered_at"
ALLOWED_CHANGEFREQ_VALUES = {
    "always",
    "hourly",
    "daily",
    "weekly",
    "monthly",
    "yearly",
    "never",
}
RESERVED_SITEMAP_PATH_PREFIXES = ("/download",)
CUSTOM_ROBOTS_PAGE_DISALLOW_PROTECTED_PREFIXES = (
    "/admin",
    "/api",
    "/assets",
    "/download",
    "/media",
    "/robots.txt",
    "/sitemap.xml",
    "/static",
    "/storage",
)
HTACCESS_CLIENT_CACHING_FIELD = "htaccess_client_caching"
MAX_HTACCESS_CACHE_TTL_SECONDS = 31_536_000
HTACCESS_CACHE_RULE_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "id": "html",
        "label": "HTML",
        "extensions": ["html", "htm"],
        "mime_types": ["text/html"],
        "default_ttl_seconds": 0,
        "default_immutable": False,
        "cache_control": "no-cache, max-age=0",
    },
    {
        "id": "styles",
        "label": "Stylesheets",
        "extensions": ["css"],
        "mime_types": ["text/css"],
        "default_ttl_seconds": 86_400,
        "default_immutable": False,
    },
    {
        "id": "scripts",
        "label": "Scripts",
        "extensions": ["js", "mjs"],
        "mime_types": ["application/javascript", "text/javascript"],
        "default_ttl_seconds": 86_400,
        "default_immutable": False,
    },
    {
        "id": "images",
        "label": "Images",
        "extensions": ["avif", "webp", "png", "jpg", "jpeg", "gif", "svg", "ico"],
        "mime_types": [
            "image/avif",
            "image/webp",
            "image/png",
            "image/jpeg",
            "image/gif",
            "image/svg+xml",
            "image/x-icon",
        ],
        "default_ttl_seconds": 2_592_000,
        "default_immutable": False,
    },
    {
        "id": "fonts",
        "label": "Fonts",
        "extensions": ["woff2", "woff", "ttf", "otf", "eot"],
        "mime_types": [
            "font/woff2",
            "font/woff",
            "font/ttf",
            "font/otf",
            "application/vnd.ms-fontobject",
        ],
        "default_ttl_seconds": 31_536_000,
        "default_immutable": True,
    },
    {
        "id": "media",
        "label": "Audio and Video",
        "extensions": ["mp4", "webm", "ogg", "mp3", "wav"],
        "mime_types": [
            "video/mp4",
            "video/webm",
            "audio/ogg",
            "video/ogg",
            "audio/mpeg",
            "audio/wav",
        ],
        "default_ttl_seconds": 2_592_000,
        "default_immutable": False,
    },
    {
        "id": "documents_data",
        "label": "Documents and Data",
        "extensions": ["pdf", "json", "xml", "txt"],
        "mime_types": [
            "application/pdf",
            "application/json",
            "application/xml",
            "text/xml",
            "text/plain",
        ],
        "default_ttl_seconds": 86_400,
        "default_immutable": False,
    },
)
HTACCESS_CACHE_RULES_BY_ID = {
    str(rule["id"]): rule for rule in HTACCESS_CACHE_RULE_DEFINITIONS
}

_MULTI_SLASH_RE = re.compile(r"/{2,}")


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _format_datetime(value: Any) -> str | None:
    dt = _parse_datetime(value)
    if not dt:
        return None
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_non_negative_int(value: Any, *, fallback: int = 0) -> int:
    try:
        normalized = int(value)
    except Exception:
        return fallback
    return max(0, normalized)


def normalize_public_base_url(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("Public base URL is required")

    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Public base URL must be an absolute http(s) URL")

    base = f"{parsed.scheme}://{parsed.netloc}"
    if parsed.path and parsed.path != "/":
        base = f"{base}{parsed.path.rstrip('/')}"
    return base


def _is_local_hostname(hostname: str) -> bool:
    host = str(hostname or "").strip().strip(".").lower()
    if not host or host == "localhost" or host.endswith(".local"):
        return True
    try:
        addr = ipaddress.ip_address(host)
        return bool(addr.is_loopback)
    except ValueError:
        return False


def _prefer_https_base_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    if parsed.scheme != "http":
        return base_url
    if _is_local_hostname(parsed.hostname or ""):
        return base_url
    return normalize_public_base_url(parsed._replace(scheme="https").geturl())


def _is_subdomain_hostname(hostname: str) -> bool:
    host = str(hostname or "").strip().strip(".").lower()
    if not host or host == "localhost" or host.endswith(".local"):
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass

    labels = [label for label in host.split(".") if label]
    # Treat www.* as canonical host (not a subdomain instance).
    if labels and labels[0] == "www":
        return False
    # mydomain.de -> 2 labels (allowed), dev.mydomain.de -> 3 labels (disabled)
    return len(labels) > 2


def is_subdomain_base_url(base_url: str) -> bool:
    try:
        parsed = urlparse(base_url)
    except Exception:
        return False
    return _is_subdomain_hostname(parsed.hostname or "")


def normalize_custom_robots_text(value: Any) -> str:
    text = str(value or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.rstrip()


def _duration_unit_for_ttl(ttl_seconds: int) -> str:
    if ttl_seconds == 0:
        return "seconds"
    if ttl_seconds % 31_536_000 == 0:
        return "years"
    if ttl_seconds % 86_400 == 0:
        return "days"
    if ttl_seconds % 3_600 == 0:
        return "hours"
    if ttl_seconds % 60 == 0:
        return "minutes"
    return "seconds"


def _format_htaccess_expires_duration(ttl_seconds: int) -> str:
    unit = _duration_unit_for_ttl(ttl_seconds)
    divisors = {
        "years": 31_536_000,
        "days": 86_400,
        "hours": 3_600,
        "minutes": 60,
        "seconds": 1,
    }
    amount = int(ttl_seconds / divisors[unit])
    singular = unit[:-1] if amount == 1 else unit
    return f"access plus {amount} {singular}"


def _default_htaccess_client_cache_rules() -> list[dict[str, Any]]:
    return [
        {
            "id": str(rule["id"]),
            "enabled": True,
            "ttl_seconds": int(rule["default_ttl_seconds"]),
            "immutable": bool(rule.get("default_immutable", False)),
        }
        for rule in HTACCESS_CACHE_RULE_DEFINITIONS
    ]


def normalize_htaccess_client_cache_rules(value: Any) -> list[dict[str, Any]]:
    defaults = {
        str(rule["id"]): rule
        for rule in _default_htaccess_client_cache_rules()
    }
    raw_rules = value if isinstance(value, list) else []
    seen_ids: set[str] = set()

    for raw_rule in raw_rules:
        if not isinstance(raw_rule, dict):
            raise ValueError("Caching rule must be an object")

        rule_id = str(raw_rule.get("id") or "").strip()
        if not rule_id or rule_id not in HTACCESS_CACHE_RULES_BY_ID:
            raise ValueError(f"Unknown caching rule id: {rule_id or 'empty'}")
        if rule_id in seen_ids:
            raise ValueError(f"Duplicate caching rule id: {rule_id}")
        seen_ids.add(rule_id)

        try:
            ttl_seconds = int(raw_rule.get("ttl_seconds"))
        except Exception:
            raise ValueError(f"Invalid ttl_seconds for caching rule {rule_id}")
        if ttl_seconds < 0 or ttl_seconds > MAX_HTACCESS_CACHE_TTL_SECONDS:
            raise ValueError(
                f"ttl_seconds for caching rule {rule_id} must be between 0 and "
                f"{MAX_HTACCESS_CACHE_TTL_SECONDS}"
            )

        defaults[rule_id] = {
            "id": rule_id,
            "enabled": bool(raw_rule.get("enabled", True)),
            "ttl_seconds": ttl_seconds,
            "immutable": bool(raw_rule.get("immutable", False)),
        }

    return [defaults[str(rule["id"])] for rule in HTACCESS_CACHE_RULE_DEFINITIONS]


def _serialize_htaccess_client_cache_rule(rule: dict[str, Any]) -> dict[str, Any]:
    definition = HTACCESS_CACHE_RULES_BY_ID[str(rule["id"])]
    ttl_seconds = int(rule.get("ttl_seconds", 0))
    immutable = bool(rule.get("immutable", False))
    cache_control = str(definition.get("cache_control") or "").strip()
    if not cache_control:
        cache_control = f"public, max-age={ttl_seconds}"
        if immutable:
            cache_control = f"{cache_control}, immutable"

    return {
        "id": str(definition["id"]),
        "label": str(definition["label"]),
        "enabled": bool(rule.get("enabled", True)),
        "ttl_seconds": ttl_seconds,
        "unit": _duration_unit_for_ttl(ttl_seconds),
        "extensions": list(definition["extensions"]),
        "mime_types": list(definition["mime_types"]),
        "immutable": immutable,
        "cache_control": cache_control,
    }


def serialize_htaccess_client_cache_rules(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = normalize_htaccess_client_cache_rules(rules)
    return [_serialize_htaccess_client_cache_rule(rule) for rule in normalized]


def render_htaccess_client_cache_rules(rules: list[dict[str, Any]]) -> str:
    serialized_rules = serialize_htaccess_client_cache_rules(rules)
    enabled_rules = [rule for rule in serialized_rules if rule["enabled"]]

    lines = [
        "# Client caching rules generated from Admin > Sitemap > Caching",
        "# Paste this block into the site's .htaccess file on Apache deployments.",
        "",
        "<IfModule mod_expires.c>",
        "  ExpiresActive On",
    ]
    for rule in enabled_rules:
        duration = _format_htaccess_expires_duration(int(rule["ttl_seconds"]))
        lines.append(f"  # {rule['label']}")
        for mime_type in rule["mime_types"]:
            lines.append(f'  ExpiresByType {mime_type} "{duration}"')
    lines.extend(["</IfModule>", "", "<IfModule mod_headers.c>"])
    for rule in enabled_rules:
        extensions = "|".join(re.escape(str(ext)) for ext in rule["extensions"])
        lines.extend(
            [
                f"  # {rule['label']}",
                f'  <FilesMatch "\\.({extensions})$">',
                f'    Header set Cache-Control "{rule["cache_control"]}"',
                "  </FilesMatch>",
            ]
        )
    lines.append("</IfModule>")
    return "\n".join(lines) + "\n"


def build_htaccess_client_caching_payload(config: Any = None) -> dict[str, Any]:
    raw_rules = (config or {}).get("rules") if isinstance(config, dict) else None
    rules = normalize_htaccess_client_cache_rules(raw_rules)
    default_rules = serialize_htaccess_client_cache_rules(_default_htaccess_client_cache_rules())
    serialized_rules = serialize_htaccess_client_cache_rules(rules)
    return {
        "rules": serialized_rules,
        "defaults": {
            "profile": "balanced",
            "rules": default_rules,
        },
        "htaccess_text": render_htaccess_client_cache_rules(rules),
    }


def _normalize_external_nav_label(value: Any) -> dict[str, str] | None:
    raw = value if isinstance(value, dict) else {}
    de = str(raw.get("de") or "").strip()
    en = str(raw.get("en") or "").strip()
    if not de and not en:
        return None
    return {"de": de, "en": en}


def _normalize_external_nav_icon(value: Any) -> str | None:
    icon = str(value or "").strip().lower()
    if not icon:
        return None
    if icon not in ALLOWED_EXTERNAL_NAV_ICONS:
        raise ValueError(
            "Invalid icon. Allowed values: "
            + ", ".join(sorted(ALLOWED_EXTERNAL_NAV_ICONS))
        )
    return icon


def normalize_external_nav_link(
    value: Any,
    *,
    fallback_order: int = 0,
    allow_generate_id: bool = False,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("External link must be an object")

    link_id = str(value.get("id") or "").strip()
    if not link_id:
        if allow_generate_id:
            link_id = f"ext-{uuid4().hex}"
        else:
            raise ValueError("External link id is required")

    raw_url = str(value.get("url") or "").strip()
    if not raw_url:
        raise ValueError("External link url is required")
    parsed = urlparse(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("External link url must be an absolute http(s) URL")

    label = _normalize_external_nav_label(value.get("label"))
    icon = _normalize_external_nav_icon(value.get("icon"))
    if bool(label) == bool(icon):
        raise ValueError("External link must define either icon or label text")

    try:
        order = int(value.get("order", fallback_order))
    except Exception:
        order = int(fallback_order)
    order = max(0, order)

    return {
        "id": link_id,
        "url": raw_url,
        "label": label,
        "icon": icon,
        "order": order,
    }


def normalize_external_nav_links(
    value: Any,
    *,
    allow_generate_ids: bool = False,
    drop_invalid: bool = False,
) -> list[dict[str, Any]]:
    raw_links = value if isinstance(value, list) else []
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for index, raw_item in enumerate(raw_links):
        try:
            link = normalize_external_nav_link(
                raw_item,
                fallback_order=index,
                allow_generate_id=allow_generate_ids,
            )
        except ValueError:
            if drop_invalid:
                continue
            raise

        if link["id"] in seen_ids:
            if allow_generate_ids:
                link["id"] = f"ext-{uuid4().hex}"
            elif drop_invalid:
                continue
            else:
                raise ValueError(f"Duplicate external link id: {link['id']}")
        seen_ids.add(link["id"])
        normalized.append(link)

    normalized.sort(key=lambda item: (int(item.get("order", 0)), str(item.get("id", ""))))
    for index, item in enumerate(normalized):
        item["order"] = index
    return normalized


def _normalize_logo_url(value: Any, *, label: str) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if any(ch.isspace() for ch in raw):
        raise ValueError(f"{label} logo URL cannot contain whitespace")

    parsed = urlparse(raw)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return raw

    if raw.startswith("/") and not raw.startswith("//") and not parsed.scheme and not parsed.netloc:
        return raw

    raise ValueError(f"{label} logo URL must be an absolute http(s) URL or root-relative path")


def normalize_footer_logo_url(value: Any) -> str | None:
    return _normalize_logo_url(value, label="Footer")


def normalize_topbar_logo_url(value: Any) -> str | None:
    return _normalize_logo_url(value, label="Topbar")


def resolve_public_base_url_from_request(request) -> str:
    request_base = normalize_public_base_url(str(request.base_url))
    forwarded_proto = str(request.headers.get("x-forwarded-proto") or "").split(",")[0].strip().lower()
    forwarded_host = str(request.headers.get("x-forwarded-host") or "").split(",")[0].strip()
    if forwarded_host:
        proto = forwarded_proto if forwarded_proto in {"http", "https"} else urlparse(request_base).scheme
        request_base = normalize_public_base_url(f"{proto}://{forwarded_host}")
    return _prefer_https_base_url(request_base)


def request_has_auth_credentials(request) -> bool:
    headers = getattr(request, "headers", {}) or {}
    authorization = str(headers.get("authorization") or "").strip()
    api_token = str(headers.get("x-api-token") or "").strip()
    return bool(authorization or api_token)


def normalize_internal_path(path: str, *, allow_root: bool = True) -> str:
    raw = str(path or "").strip()
    if not raw:
        raise ValueError("Path is required")

    if "://" in raw:
        raise ValueError("Expected an internal path, got URL")

    raw = raw.split("?", 1)[0].split("#", 1)[0].strip()
    raw = _MULTI_SLASH_RE.sub("/", raw)
    if not raw.startswith("/"):
        raw = f"/{raw}"
    if len(raw) > 1:
        raw = raw.rstrip("/")
    if any(ch.isspace() for ch in raw):
        raise ValueError("Path cannot contain whitespace")
    if ".." in raw:
        raise ValueError("Path cannot contain '..'")
    if raw == "/" and not allow_root:
        raise ValueError("Root path is not allowed here")
    return raw


def normalize_redirect_source_path(path: str) -> str:
    """
    Normalize redirect source paths.

    Supports wildcard source patterns using:
    - `*` for zero or more characters
    - `?` for exactly one character
    """
    raw = str(path or "").strip()
    if not raw:
        raise ValueError("Path is required")

    if "://" in raw:
        raise ValueError("Expected an internal path, got URL")

    raw = _MULTI_SLASH_RE.sub("/", raw)
    if not raw.startswith("/"):
        raw = f"/{raw}"
    if len(raw) > 1:
        raw = raw.rstrip("/")
    if any(ch.isspace() for ch in raw):
        raise ValueError("Path cannot contain whitespace")
    if ".." in raw:
        raise ValueError("Path cannot contain '..'")
    if "#" in raw:
        raise ValueError("Path cannot contain '#'")
    return raw


def is_external_url(value: str) -> bool:
    raw = str(value or "").strip().lower()
    return raw.startswith("http://") or raw.startswith("https://")


def normalize_redirect_target(target: str | None, *, allow_empty: bool = False) -> str | None:
    raw = str(target or "").strip()
    if not raw:
        if allow_empty:
            return None
        raise ValueError("Target is required")

    if is_external_url(raw):
        parsed = urlparse(raw)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Invalid external redirect URL")
        return raw

    return normalize_internal_path(raw)


def normalize_redirect_status_code(status_code: int) -> int:
    code = int(status_code)
    if code not in ALLOWED_REDIRECT_STATUS_CODES:
        raise ValueError(
            "Unsupported redirect status code. Allowed: "
            + ", ".join(str(c) for c in sorted(ALLOWED_REDIRECT_STATUS_CODES))
        )
    return code


def slug_to_path(slug: str | None) -> str:
    value = str(slug or "").strip("/")
    if not value or value == "landing":
        return "/"
    return f"/{value}"


def _is_reserved_sitemap_path(path: str) -> bool:
    normalized = normalize_internal_path(path)
    return any(
        normalized == prefix or normalized.startswith(f"{prefix}/")
        for prefix in RESERVED_SITEMAP_PATH_PREFIXES
    )


def _slug_depth(slug: str) -> int:
    if slug == "landing":
        return 0
    return slug.count("/") + 1


def default_priority_for_slug(slug: str) -> float:
    depth = _slug_depth(slug)
    if depth <= 0:
        return 1.0
    if depth == 1:
        return 0.8
    if depth == 2:
        return 0.5
    return 0.2


def _normalize_priority(value: Any, *, fallback: float) -> float:
    if value is None:
        return fallback
    try:
        priority = float(value)
    except Exception:
        return fallback
    if priority != priority:  # NaN guard
        return fallback
    return max(0.0, min(1.0, priority))


def _format_priority(value: float) -> str:
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    if "." not in text:
        text = f"{text}.0"
    return text


def _normalize_changefreq(value: Any) -> str | None:
    raw = str(value or "").strip().lower()
    if not raw:
        return None
    return raw if raw in ALLOWED_CHANGEFREQ_VALUES else None


def _normalize_slug(value: Any) -> str | None:
    slug = str(value or "").strip("/")
    if not slug:
        return None
    return slug


def _normalize_page_status(value: Any, *, fallback: str = "hidden") -> str:
    raw = str(value or "").strip().lower()
    if raw == "draft":
        return "hidden"
    if raw in {"init", "hidden", "published", "under_construction"}:
        return raw
    return fallback


def _is_hidden_like_page_status(status: str) -> bool:
    return status in {"hidden", "init"}


def _compute_effective_page_status(doc: dict) -> str:
    now = datetime.now(timezone.utc)
    base_status = _normalize_page_status(doc.get("status"), fallback="hidden")
    publish_at = _parse_datetime(doc.get("publish_at"))
    unpublish_at = _parse_datetime(doc.get("unpublish_at"))

    if unpublish_at and unpublish_at <= now:
        return "hidden"
    if publish_at:
        if publish_at > now:
            return "hidden"
        if _is_hidden_like_page_status(base_status):
            # Scheduled draft/hidden/init pages become published.
            return "published"
    if base_status == "init":
        return "hidden"
    return base_status


def is_page_publicly_visible(doc: dict) -> bool:
    return _compute_effective_page_status(doc) in {"published", "under_construction"}


def _is_same_or_descendant_slug(candidate_slug: str, root_slug: str) -> bool:
    if root_slug == "landing":
        return True
    return candidate_slug == root_slug or candidate_slug.startswith(f"{root_slug}/")


def _collect_hidden_subtree_roots(pages: list[dict]) -> list[str]:
    roots = []
    for page in pages:
        if not page.get("hide_subtree_from_sitemap", False):
            continue
        slug = _normalize_slug(page.get("slug"))
        if not slug:
            continue
        roots.append(slug)

    deduped_sorted = sorted(set(roots), key=lambda slug: (slug.count("/"), slug))
    filtered: list[str] = []
    for root in deduped_sorted:
        if any(_is_same_or_descendant_slug(root, existing) for existing in filtered):
            continue
        filtered.append(root)
    return filtered


def _is_hidden_by_any_subtree(slug: str, hidden_roots: list[str]) -> bool:
    return any(_is_same_or_descendant_slug(slug, root) for root in hidden_roots)


def _filter_pages_with_existing_slug_ancestry(pages: list[dict]) -> list[dict]:
    page_by_slug: dict[str, dict] = {}
    ordered_pages: list[tuple[str, dict]] = []
    for page in pages:
        slug = _normalize_slug(page.get("slug"))
        if not slug:
            continue
        page_by_slug[slug] = page
        ordered_pages.append((slug, page))

    existing_slugs = set(page_by_slug.keys())
    filtered: list[dict] = []
    for slug, page in ordered_pages:
        if slug == "landing":
            filtered.append(page)
            continue
        parts = slug.split("/")
        ancestor_slugs = ("/".join(parts[:index]) for index in range(1, len(parts)))
        if all(ancestor in existing_slugs for ancestor in ancestor_slugs):
            filtered.append(page)
    return filtered


def _sort_robots_path(path: str) -> tuple[int, int, str]:
    return (0 if path == "/" else 1, len(path), path)


def _collect_hidden_robots_paths(pages: list[dict]) -> tuple[list[str], list[str]]:
    hidden_subtree_roots = _collect_hidden_subtree_roots(pages)
    disallow_paths: set[str] = {"/download/"}
    allow_paths: set[str] = set()

    for root_slug in hidden_subtree_roots:
        root_path = slug_to_path(root_slug)
        disallow_paths.add(root_path)
        if root_path != "/":
            disallow_paths.add(f"{root_path}/")

    for page in pages:
        slug = _normalize_slug(page.get("slug"))
        if not slug:
            continue
        if _is_reserved_sitemap_path(slug_to_path(slug)):
            continue
        if not page.get("hide_from_sitemap", False):
            continue
        if _is_hidden_by_any_subtree(slug, hidden_subtree_roots):
            continue
        path = slug_to_path(slug)
        disallow_paths.add(path)
        if path != "/":
            allow_paths.add(f"{path}/")

    allow_paths.difference_update(disallow_paths)
    return (
        sorted(disallow_paths, key=_sort_robots_path),
        sorted(allow_paths, key=_sort_robots_path),
    )


def _collect_hidden_disallow_paths(pages: list[dict]) -> list[str]:
    disallow_paths, _allow_paths = _collect_hidden_robots_paths(pages)
    return disallow_paths


def _collect_live_page_paths_for_robots(pages: list[dict]) -> set[str]:
    paths: set[str] = set()
    for page in pages:
        slug = _normalize_slug(page.get("slug"))
        if not slug:
            continue

        path = normalize_internal_path(slug_to_path(slug))
        if _is_reserved_sitemap_path(path):
            continue

        paths.add(path)
        if path == "/":
            paths.add("/en")
        else:
            paths.add(normalize_internal_path(f"/en{path}"))
    return paths


def _is_protected_custom_robots_disallow_path(path: str) -> bool:
    if path == "/":
        return True
    if any(
        path == prefix or path.startswith(f"{prefix}/")
        for prefix in CUSTOM_ROBOTS_PAGE_DISALLOW_PROTECTED_PREFIXES
    ):
        return True
    return any("." in segment for segment in path.split("/") if segment)


def _custom_robots_page_rule_path(
    value: str,
    *,
    public_base_url: str | None = None,
) -> str | None:
    raw = str(value or "").split("#", 1)[0].strip()
    if not raw:
        return None
    if any(marker in raw for marker in ("*", "$", "?")):
        return None
    if "://" in raw:
        try:
            parsed_rule_url = urlparse(raw)
            parsed_base_url = urlparse(public_base_url or "")
        except Exception:
            return None
        if (
            not parsed_rule_url.scheme
            or not parsed_rule_url.netloc
            or parsed_rule_url.netloc != parsed_base_url.netloc
        ):
            return None
        raw = parsed_rule_url.path or "/"
    elif not raw.startswith("/"):
        return None
    try:
        path = normalize_internal_path(raw)
    except ValueError:
        return None
    if _is_protected_custom_robots_disallow_path(path):
        return None
    return path


def remove_stale_custom_page_disallows(
    custom_text: str,
    pages: list[dict],
    *,
    public_base_url: str | None = None,
) -> tuple[str, list[str]]:
    normalized_text = normalize_custom_robots_text(custom_text)
    if not normalized_text:
        return "", []

    live_page_paths = _collect_live_page_paths_for_robots(pages)
    kept_lines: list[str] = []
    stale_paths: set[str] = set()

    for line in normalized_text.split("\n"):
        name, separator, value = line.partition(":")
        directive = name.strip().lower()
        if not separator or directive not in {"allow", "disallow"}:
            kept_lines.append(line)
            continue

        path = _custom_robots_page_rule_path(value, public_base_url=public_base_url)
        if path and path not in live_page_paths:
            stale_paths.add(path)
            continue

        kept_lines.append(line)

    return "\n".join(kept_lines).rstrip(), sorted(stale_paths)


def _build_sitemap_entries(pages: list[dict], *, public_base_url: str) -> list[dict]:
    hidden_subtree_roots = _collect_hidden_subtree_roots(pages)
    by_path: dict[str, dict] = {}

    for page in pages:
        slug = _normalize_slug(page.get("slug"))
        if not slug:
            continue
        if not is_page_publicly_visible(page):
            continue
        if page.get("hide_from_sitemap", False):
            continue
        if _is_hidden_by_any_subtree(slug, hidden_subtree_roots):
            continue
        if page.get("redirect_to"):
            # Redirect pages are canonicalized to their target.
            continue

        path = slug_to_path(slug)
        if _is_reserved_sitemap_path(path):
            continue
        loc = f"{public_base_url}{path}" if path != "/" else f"{public_base_url}/"
        en_path = "/en" if path == "/" else f"/en{path}"
        lastmod = _format_datetime(page.get("updated_at") or page.get("created_at"))
        priority = _normalize_priority(
            page.get("sitemap_priority"),
            fallback=default_priority_for_slug(slug),
        )
        changefreq = _normalize_changefreq(page.get("sitemap_changefreq"))
        by_path[path] = {
            "path": path,
            "loc": loc,
            "lastmod": lastmod,
            "priority": priority,
            "changefreq": changefreq,
            "alternates": {
                "de": loc,
                "en": f"{public_base_url}{en_path}",
                "x-default": loc,
            },
        }

    return [by_path[path] for path in sorted(by_path.keys())]


def render_sitemap_xml(entries: list[dict]) -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">',
    ]
    for entry in entries:
        lines.append("  <url>")
        lines.append(f"    <loc>{escape(entry['loc'])}</loc>")
        alternates = entry.get("alternates") if isinstance(entry, dict) else None
        if isinstance(alternates, dict):
            for hreflang in ("de", "en", "x-default"):
                href = alternates.get(hreflang)
                if not href:
                    continue
                lines.append(
                    f'    <xhtml:link rel="alternate" hreflang="{hreflang}" href="{escape(str(href))}" />'
                )
        if entry.get("lastmod"):
            lines.append(f"    <lastmod>{entry['lastmod']}</lastmod>")
        if entry.get("changefreq"):
            lines.append(f"    <changefreq>{entry['changefreq']}</changefreq>")
        lines.append(f"    <priority>{_format_priority(float(entry.get('priority', 0.2)))}</priority>")
        lines.append("  </url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def _render_automatic_robots_text(
    *,
    public_base_url: str,
    hidden_disallow_paths: list[str],
    hidden_allow_paths: list[str],
    subdomain: bool,
) -> str:
    lines = [
        "# AUTO-GENERATED RULES (read-only)",
        "User-agent: *",
    ]
    if subdomain:
        lines.append("Disallow: /")
        return "\n".join(lines) + "\n"

    if "/" in hidden_disallow_paths:
        lines.append("Disallow: /")
        lines.append("Disallow: /download/")
    else:
        lines.append("Allow: /")
        for path in hidden_disallow_paths:
            lines.append(f"Disallow: {path}")
        for path in hidden_allow_paths:
            lines.append(f"Allow: {path}")

    sitemap_url = f"{public_base_url}/sitemap.xml"
    lines.append(f"Sitemap: {sitemap_url}")
    return "\n".join(lines) + "\n"


def merge_robots_text(automatic_text: str, custom_text: str) -> str:
    custom = normalize_custom_robots_text(custom_text)
    automatic = str(automatic_text or "").rstrip()
    if not custom:
        return f"{automatic}\n" if automatic else ""
    if not automatic:
        return f"{custom}\n"
    return (
        f"{automatic}\n\n"
        "# CUSTOM RULES (editable in Admin)\n"
        f"{custom}\n"
    )


async def get_custom_robots_text(db) -> str:
    coll = db[SITEMAP_CONFIG_COLLECTION]
    doc = await coll.find_one({"key": ADMIN_SITEMAP_CONFIG_KEY}, {"custom_robots_txt": 1})
    return normalize_custom_robots_text((doc or {}).get("custom_robots_txt"))


async def get_navigation_links_config(db) -> dict[str, Any]:
    coll = db[SITEMAP_CONFIG_COLLECTION]
    doc = await coll.find_one(
        {"key": ADMIN_SITEMAP_CONFIG_KEY},
        {
            "nav_external_links": 1,
            "footer_external_links": 1,
            "topbar_logo_url": 1,
            "footer_logo_url": 1,
        },
    )
    payload = doc or {}
    try:
        if "topbar_logo_url" in payload:
            topbar_logo_url = normalize_topbar_logo_url(payload.get("topbar_logo_url"))
        else:
            design_doc = await db[DESIGN_CONFIG_COLLECTION].find_one(
                {"key": LEGACY_DESIGN_SETTINGS_KEY},
                {"topbar_logo_url": 1},
            )
            topbar_logo_url = normalize_topbar_logo_url((design_doc or {}).get("topbar_logo_url"))
    except ValueError:
        topbar_logo_url = None
    try:
        footer_logo_url = normalize_footer_logo_url(payload.get("footer_logo_url"))
    except ValueError:
        footer_logo_url = None
    result = {
        "nav_external_links": normalize_external_nav_links(
            payload.get("nav_external_links"),
            allow_generate_ids=True,
            drop_invalid=True,
        ),
        "footer_external_links": normalize_external_nav_links(
            payload.get("footer_external_links"),
            allow_generate_ids=True,
            drop_invalid=True,
        ),
        "topbar_logo_url": topbar_logo_url,
        "footer_logo_url": footer_logo_url,
    }
    image_urls = collect_raster_image_urls_from_payload(result)
    if image_urls:
        asset_docs_by_url = await fetch_asset_docs_by_urls(db, image_urls)
        if asset_docs_by_url:
            enrich_raster_payload_with_asset_docs(result, asset_docs_by_url)
    return result


async def build_public_robots_payload(
    db,
    *,
    public_base_url: str,
    custom_robots_txt: str = "",
) -> dict:
    normalized_base_url = normalize_public_base_url(public_base_url)
    subdomain = is_subdomain_base_url(normalized_base_url)
    pages: list[dict] = []
    robots_pages: list[dict] = []
    hidden_disallow_paths: list[str] = []
    hidden_allow_paths: list[str] = []
    if not subdomain:
        raw_pages = await db[PAGES_COLLECTION].find({}).to_list(length=5000)
        pages = _filter_pages_with_existing_slug_ancestry(raw_pages)
        robots_pages = [page for page in pages if is_page_publicly_visible(page)]
        hidden_disallow_paths, hidden_allow_paths = _collect_hidden_robots_paths(robots_pages)
    automatic_text = _render_automatic_robots_text(
        public_base_url=normalized_base_url,
        hidden_disallow_paths=hidden_disallow_paths,
        hidden_allow_paths=hidden_allow_paths,
        subdomain=subdomain,
    )
    stale_custom_disallow_paths: list[str] = []
    if subdomain:
        custom_text = normalize_custom_robots_text(custom_robots_txt)
    else:
        custom_text, stale_custom_disallow_paths = remove_stale_custom_page_disallows(
            custom_robots_txt,
            robots_pages,
            public_base_url=normalized_base_url,
        )
    merged_text = merge_robots_text(automatic_text, custom_text)
    parsed = urlparse(normalized_base_url)
    return {
        "enabled": True,
        "public_base_url": normalized_base_url,
        "subdomain_disallow_all": subdomain,
        "subdomain_host": (parsed.hostname or "") if subdomain else None,
        "hidden_disallow_paths": hidden_disallow_paths,
        "hidden_allow_paths": hidden_allow_paths,
        "automatic_text": automatic_text,
        "custom_text": custom_text,
        "stale_custom_disallow_paths": stale_custom_disallow_paths,
        "merged_text": merged_text,
    }


async def build_public_sitemap_payload(db, *, public_base_url: str) -> dict:
    normalized_base_url = normalize_public_base_url(public_base_url)
    generated_at = _format_datetime(datetime.now(timezone.utc))

    if is_subdomain_base_url(normalized_base_url):
        parsed = urlparse(normalized_base_url)
        return {
            "enabled": False,
            "disabled_reason": "subdomain_instance",
            "disabled_host": parsed.hostname or "",
            "public_base_url": normalized_base_url,
            "generated_at": generated_at,
            "page_count": 0,
            "orphaned_page_count": 0,
            "entry_count": 0,
            "hidden_subtree_roots": [],
            "entries": [],
            "xml": "",
        }

    raw_pages = await db[PAGES_COLLECTION].find({}).to_list(length=5000)
    pages = _filter_pages_with_existing_slug_ancestry(raw_pages)
    entries = _build_sitemap_entries(pages, public_base_url=normalized_base_url)
    hidden_subtree_roots = _collect_hidden_subtree_roots(pages)
    return {
        "enabled": True,
        "disabled_reason": None,
        "disabled_host": None,
        "public_base_url": normalized_base_url,
        "generated_at": generated_at,
        "page_count": len(pages),
        "orphaned_page_count": len(raw_pages) - len(pages),
        "entry_count": len(entries),
        "hidden_subtree_roots": [slug_to_path(slug) for slug in hidden_subtree_roots],
        "entries": entries,
        "xml": render_sitemap_xml(entries),
    }


def serialize_redirect_doc(doc: dict, *, now: datetime | None = None) -> dict:
    current = now or datetime.now(timezone.utc)
    expires_at = _parse_datetime(doc.get("expires_at"))
    enabled = bool(doc.get("is_active", True))
    expired = bool(expires_at and expires_at <= current)
    active = enabled and not expired
    status_code = int(doc.get("status_code", 301))
    target_path = doc.get("target_path")
    if target_path is None and status_code != 410:
        target_path = "/"
    if target_path is not None:
        target_path = str(target_path)

    return {
        "id": str(doc.get("_id")),
        "source_path": doc.get("source_path", "/"),
        "target_path": target_path,
        "status_code": status_code,
        "kind": doc.get("kind", "custom"),
        "generated_reason": doc.get("generated_reason"),
        "generated_from_path": doc.get("generated_from_path"),
        "generated_to_path": doc.get("generated_to_path"),
        "is_enabled": enabled,
        "is_expired": expired,
        "is_active": active,
        "expires_at": _format_datetime(expires_at),
        "anonymous_hit_count": _normalize_non_negative_int(
            doc.get(REDIRECT_ANONYMOUS_HIT_COUNT_FIELD),
            fallback=0,
        ),
        "last_triggered_at": _format_datetime(doc.get(REDIRECT_LAST_TRIGGERED_AT_FIELD)),
        "created_by": doc.get("created_by"),
        "created_at": _format_datetime(doc.get("created_at")),
        "updated_at": _format_datetime(doc.get("updated_at")),
    }


async def increment_redirect_anonymous_hit_count(
    db,
    *,
    redirect_doc: dict | None,
    now: datetime | None = None,
) -> None:
    if not isinstance(redirect_doc, dict):
        return
    redirect_id = redirect_doc.get("_id")
    if not redirect_id:
        return
    ts = now or datetime.now(timezone.utc)
    await db[REDIRECTS_COLLECTION].update_one(
        {"_id": redirect_id},
        {
            "$inc": {REDIRECT_ANONYMOUS_HIT_COUNT_FIELD: 1},
            "$set": {REDIRECT_LAST_TRIGGERED_AT_FIELD: ts},
        },
    )


def _active_redirect_query(*, source_path: str | None, now: datetime) -> dict:
    query: dict[str, Any] = {
        "is_active": {"$ne": False},
        "$or": [
            {"expires_at": {"$exists": False}},
            {"expires_at": None},
            {"expires_at": {"$gt": now}},
        ],
    }
    if source_path is not None:
        query["source_path"] = source_path
    return query


def _redirect_source_contains_wildcards(source_path: str) -> bool:
    text = str(source_path or "")
    return "*" in text or "?" in text


def _redirect_source_pattern_matches(source_pattern: str, source_path: str) -> bool:
    pattern = str(source_pattern or "")
    path = str(source_path or "")
    if not pattern:
        return False
    if not _redirect_source_contains_wildcards(pattern):
        return pattern == path
    wildcard_regex = "^" + re.escape(pattern).replace(r"\*", ".*").replace(r"\?", ".") + "$"
    return re.fullmatch(wildcard_regex, path) is not None


def _redirect_pattern_specificity(source_pattern: str) -> tuple[int, int, int]:
    text = str(source_pattern or "")
    wildcard_count = text.count("*") + text.count("?")
    literal_count = len(text) - wildcard_count
    return (literal_count, -wildcard_count, len(text))


async def find_active_redirect_doc(db, *, source_path: str) -> dict | None:
    now = datetime.now(timezone.utc)
    coll = db[REDIRECTS_COLLECTION]
    exact = await coll.find_one(_active_redirect_query(source_path=source_path, now=now))
    if exact:
        return exact

    wildcard_candidates = await coll.find(
        {
            **_active_redirect_query(source_path=None, now=now),
            "source_path": {"$regex": r"[*?]"},
        }
    ).to_list(length=5000)

    best_match = None
    best_rank = None
    for candidate in wildcard_candidates:
        pattern = str(candidate.get("source_path") or "")
        if not _redirect_source_pattern_matches(pattern, source_path):
            continue
        updated_at = _parse_datetime(candidate.get("updated_at")) or datetime.fromtimestamp(0, tz=timezone.utc)
        rank = (_redirect_pattern_specificity(pattern), updated_at)
        if best_rank is None or rank > best_rank:
            best_rank = rank
            best_match = candidate

    return best_match


async def upsert_generated_redirects_for_slug_mapping(
    db,
    slug_mapping: dict[str, str],
    *,
    reason: str = "moved_subtree",
) -> dict:
    coll = db[REDIRECTS_COLLECTION]
    now = datetime.now(timezone.utc)

    created = 0
    updated = 0
    skipped_custom = 0
    skipped_unchanged = 0

    for old_slug, new_slug in sorted(slug_mapping.items()):
        source_path = slug_to_path(old_slug)
        target_path = slug_to_path(new_slug)
        if source_path == target_path:
            skipped_unchanged += 1
            continue

        existing = await coll.find_one({"source_path": source_path})
        if existing and existing.get("kind") == "custom":
            skipped_custom += 1
            continue

        payload = {
            "source_path": source_path,
            "target_path": target_path,
            "status_code": 301,
            "kind": "generated",
            "generated_reason": reason,
            "generated_from_path": source_path,
            "generated_to_path": target_path,
            "is_active": True,
            REDIRECT_ANONYMOUS_HIT_COUNT_FIELD: 0,
            "updated_at": now,
        }

        if existing:
            await coll.update_one({"_id": existing["_id"]}, {"$set": payload})
            updated += 1
            continue

        await coll.insert_one({**payload, "created_at": now, "created_by": "system"})
        created += 1

    return {
        "created": created,
        "updated": updated,
        "skipped_custom": skipped_custom,
        "skipped_unchanged": skipped_unchanged,
    }


async def upsert_generated_gone_redirect_for_slug(
    db,
    slug: str,
    *,
    reason: str = "deleted_public_page",
) -> dict:
    coll = db[REDIRECTS_COLLECTION]
    now = datetime.now(timezone.utc)
    source_path = slug_to_path(slug)

    existing = await coll.find_one({"source_path": source_path})
    if existing and existing.get("kind") == "custom":
        return {"created": 0, "updated": 0, "skipped_custom": 1}

    payload = {
        "source_path": source_path,
        "target_path": None,
        "status_code": 410,
        "kind": "generated",
        "generated_reason": reason,
        "generated_from_path": source_path,
        "generated_to_path": None,
        "is_active": True,
        REDIRECT_ANONYMOUS_HIT_COUNT_FIELD: 0,
        "updated_at": now,
    }

    if existing:
        await coll.update_one({"_id": existing["_id"]}, {"$set": payload})
        return {"created": 0, "updated": 1, "skipped_custom": 0}

    await coll.insert_one({**payload, "created_at": now, "created_by": "system"})
    return {"created": 1, "updated": 0, "skipped_custom": 0}
