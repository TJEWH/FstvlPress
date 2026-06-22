from __future__ import annotations

import io
import re
from xml.etree import ElementTree as ET

from PIL import ExifTags, Image

XMP_PACKET_RE = re.compile(
    rb"<(?:x:xmpmeta|xmpmeta)[^>]*>.*?</(?:x:xmpmeta|xmpmeta)>",
    re.IGNORECASE | re.DOTALL,
)

XMP_NS = {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "dc": "http://purl.org/dc/elements/1.1/",
    "xmp": "http://ns.adobe.com/xap/1.0/",
    "xmpRights": "http://ns.adobe.com/xap/1.0/rights/",
    "photoshop": "http://ns.adobe.com/photoshop/1.0/",
    "lr": "http://ns.adobe.com/lightroom/1.0/",
}
XMP_URI_TO_PREFIX = {uri: prefix for prefix, uri in XMP_NS.items()}


def _clean_text(value) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return re.sub(r"\s+", " ", text)


def _decode_exif_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        # Windows EXIF XP* fields are UTF-16LE null-terminated.
        try:
            text = value.decode("utf-16-le", errors="ignore").replace("\x00", "")
            text = _clean_text(text)
            if text:
                return text
        except Exception:
            pass
        try:
            return _clean_text(value.decode("utf-8", errors="ignore"))
        except Exception:
            return ""
    if isinstance(value, (list, tuple)):
        return _clean_text(", ".join(_decode_exif_value(item) for item in value if item is not None))
    return _clean_text(value)


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        item = _clean_text(value)
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _append_raw_value(target: dict[str, list[str]], key: str, value) -> None:
    name = _clean_text(key)
    if not name:
        return
    text = _clean_text(value)
    if not text:
        return
    existing = target.setdefault(name, [])
    if text.lower() not in {entry.lower() for entry in existing}:
        existing.append(text)


def _xml_name(name: str) -> str:
    raw = str(name or "")
    if raw.startswith("{") and "}" in raw:
        uri, local = raw[1:].split("}", 1)
        prefix = XMP_URI_TO_PREFIX.get(uri)
        if prefix:
            return f"{prefix}:{local}"
        return local
    return raw


def _extract_raw_xmp_fields(packet: str) -> dict[str, list[str]]:
    raw: dict[str, list[str]] = {}
    try:
        root = ET.fromstring(packet)
    except Exception:
        return raw

    for elem in root.iter():
        elem_name = _xml_name(elem.tag)
        text = _clean_text(elem.text)
        if text:
            _append_raw_value(raw, f"xmp:{elem_name}", text)
        for attr_name, attr_value in elem.attrib.items():
            _append_raw_value(raw, f"xmp:{elem_name}@{_xml_name(attr_name)}", attr_value)
    return raw


def _merge_raw_map(target: dict[str, list[str]], source: dict[str, list[str]]) -> dict[str, list[str]]:
    for key, values in (source or {}).items():
        for value in values or []:
            _append_raw_value(target, key, value)
    return target


def _extract_raw_info_fields(info: dict) -> dict[str, list[str]]:
    raw: dict[str, list[str]] = {}
    if not isinstance(info, dict):
        return raw

    for key, value in info.items():
        info_key = f"info:{_clean_text(key)}"
        if isinstance(value, (str, int, float, bool)):
            _append_raw_value(raw, info_key, value)
        elif isinstance(value, bytes):
            _append_raw_value(raw, info_key, f"<bytes:{len(value)}>")
        elif isinstance(value, (list, tuple)):
            for item in value:
                if isinstance(item, (str, int, float, bool)):
                    _append_raw_value(raw, info_key, item)
                elif isinstance(item, bytes):
                    _append_raw_value(raw, info_key, f"<bytes:{len(item)}>")
        elif isinstance(value, dict):
            for sub_key, sub_value in value.items():
                if isinstance(sub_value, (str, int, float, bool)):
                    _append_raw_value(raw, f"{info_key}.{_clean_text(sub_key)}", sub_value)
                elif isinstance(sub_value, bytes):
                    _append_raw_value(raw, f"{info_key}.{_clean_text(sub_key)}", f"<bytes:{len(sub_value)}>")
    return raw


def _extract_xmp_packets(data: bytes) -> list[str]:
    packets = []
    for match in XMP_PACKET_RE.findall(data or b""):
        packet = match.decode("utf-8", errors="ignore").strip()
        if packet:
            packets.append(packet)
    return packets


def _extract_from_xmp_packet(packet: str) -> dict:
    authors: list[str] = []
    rights: list[str] = []
    keywords: list[str] = []
    tools: list[str] = []
    credits: list[str] = []

    try:
        root = ET.fromstring(packet)
    except Exception:
        return {
            "authors": [],
            "rights": [],
            "keywords": [],
            "tools": [],
            "credits": [],
        }

    authors.extend(_clean_text(node.text) for node in root.findall(".//dc:creator//rdf:li", XMP_NS))
    rights.extend(_clean_text(node.text) for node in root.findall(".//dc:rights//rdf:li", XMP_NS))
    rights.extend(_clean_text(node.text) for node in root.findall(".//xmpRights:UsageTerms//rdf:li", XMP_NS))
    keywords.extend(_clean_text(node.text) for node in root.findall(".//dc:subject//rdf:li", XMP_NS))
    keywords.extend(_clean_text(node.text) for node in root.findall(".//lr:hierarchicalSubject//rdf:li", XMP_NS))
    keywords.extend(_clean_text(node.text) for node in root.findall(".//photoshop:SupplementalCategories//rdf:li", XMP_NS))

    for desc in root.findall(".//rdf:Description", XMP_NS):
        creator_tool = _clean_text(desc.get(f"{{{XMP_NS['xmp']}}}CreatorTool"))
        if creator_tool:
            tools.append(creator_tool)

        credit = _clean_text(desc.get(f"{{{XMP_NS['photoshop']}}}Credit"))
        if credit:
            credits.append(credit)

        xmp_author = _clean_text(desc.get(f"{{{XMP_NS['photoshop']}}}AuthorsPosition"))
        if xmp_author:
            authors.append(xmp_author)

        copyright_notice = _clean_text(desc.get(f"{{{XMP_NS['photoshop']}}}Copyright"))
        if copyright_notice:
            rights.append(copyright_notice)

        web_statement = _clean_text(desc.get(f"{{{XMP_NS['xmpRights']}}}WebStatement"))
        if web_statement:
            rights.append(web_statement)

        marked = _clean_text(desc.get(f"{{{XMP_NS['xmpRights']}}}Marked"))
        if marked:
            rights.append(marked)

    return {
        "authors": _dedupe(authors),
        "rights": _dedupe(rights),
        "keywords": _dedupe(keywords),
        "tools": _dedupe(tools),
        "credits": _dedupe(credits),
    }


def extract_image_metadata(data: bytes, content_type: str) -> dict:
    """
    Extract rights/authorship-oriented metadata from common image standards.
    Supports EXIF and XMP blocks commonly written by Photoshop, Lightroom, and Affinity.
    """
    if not content_type.startswith("image/"):
        return {
            "authors": [],
            "rights": [],
            "keywords": [],
            "tools": [],
            "credits": [],
            "raw_exif": {},
            "raw_xmp": {},
            "raw_info": {},
        }

    authors: list[str] = []
    rights: list[str] = []
    keywords: list[str] = []
    tools: list[str] = []
    credits: list[str] = []
    raw_exif: dict[str, list[str]] = {}
    raw_xmp: dict[str, list[str]] = {}
    raw_info: dict[str, list[str]] = {}

    try:
        with Image.open(io.BytesIO(data)) as img:
            raw_info = _extract_raw_info_fields(getattr(img, "info", {}))
            exif = img.getexif() if hasattr(img, "getexif") else None
            if exif:
                for key, value in exif.items():
                    tag = ExifTags.TAGS.get(key, str(key))
                    text = _decode_exif_value(value)
                    if not text:
                        continue
                    _append_raw_value(raw_exif, f"exif:{tag}", text)
                    lowered = str(tag).strip().lower()
                    if lowered in {"artist", "author", "xpauthor"}:
                        authors.append(text)
                    elif lowered in {"copyright"}:
                        rights.append(text)
                    elif lowered in {"xpkeywords"}:
                        keywords.extend([item.strip() for item in text.split(";") if item.strip()])
                    elif lowered in {"software"}:
                        tools.append(text)
                    elif lowered in {"imagedescription"}:
                        credits.append(text)
    except Exception:
        # Metadata extraction must not block upload flow.
        pass

    for packet in _extract_xmp_packets(data):
        parsed = _extract_from_xmp_packet(packet)
        authors.extend(parsed["authors"])
        rights.extend(parsed["rights"])
        keywords.extend(parsed["keywords"])
        tools.extend(parsed["tools"])
        credits.extend(parsed["credits"])
        _merge_raw_map(raw_xmp, _extract_raw_xmp_fields(packet))

    return {
        "authors": _dedupe(authors),
        "rights": _dedupe(rights),
        "keywords": _dedupe(keywords),
        "tools": _dedupe(tools),
        "credits": _dedupe(credits),
        "raw_exif": raw_exif,
        "raw_xmp": raw_xmp,
        "raw_info": raw_info,
    }
