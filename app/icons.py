"""Inline SVG line icons (Lucide-style). Returned as Markup so Jinja doesn't escape
them. All use stroke="currentColor", so they inherit the element's text color and work
in both themes automatically."""
from markupsafe import Markup

_WRAP = (
    '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" '
    'width="18" height="18">{}</svg>'
)

_PATHS = {
    "image": '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/>'
             '<path d="m21 15-3.09-3.09a2 2 0 0 0-2.83 0L6 21"/>',
    "video": '<rect x="2" y="2" width="20" height="20" rx="2"/>'
             '<path d="M7 2v20M17 2v20M2 12h20M2 7h5M2 17h5M17 17h5M17 7h5"/>',
    "audio": '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
    "archive": '<rect width="20" height="5" x="2" y="3" rx="1"/>'
               '<path d="M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8"/><path d="M10 12h4"/>',
    "spreadsheet": '<rect width="18" height="18" x="3" y="3" rx="2"/>'
                   '<path d="M12 3v18M3 9h18M3 15h18"/>',
    "document": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7z"/>'
                '<path d="M14 2v5h5"/><path d="M16 13H8M16 17H8M10 9H8"/>',
    "file": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7z"/><path d="M14 2v5h5"/>',
    "copy": '<rect width="14" height="14" x="8" y="8" rx="2"/>'
            '<path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "upload": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>'
              '<path d="M17 8l-5-5-5 5"/><path d="M12 3v12"/>',
    "trash": '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>'
             '<path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M10 11v6M14 11v6"/>',
    # Chevron points UP (ascending); the ".desc" CSS class rotates it 180deg for descending.
    "chevron": '<path d="m18 15-6-6-6 6"/>',
    # Horizontal "more" dots for the row action (kebab) button. Filled so they read as dots.
    "more": '<circle cx="5" cy="12" r="1.6" fill="currentColor"/>'
            '<circle cx="12" cy="12" r="1.6" fill="currentColor"/>'
            '<circle cx="19" cy="12" r="1.6" fill="currentColor"/>',
    "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>'
                '<path d="M7 10l5 5 5-5"/><path d="M12 15V3"/>',
    "close": '<path d="M18 6 6 18"/><path d="M6 6l12 12"/>',
    # Horizontal lines in ascending length (short→long): "smallest first" convention.
    "sort-asc": '<path d="M4 6h6"/><path d="M4 12h12"/><path d="M4 18h18"/>',
    # Horizontal lines in descending length (long→short): "largest first" convention.
    "sort-desc": '<path d="M4 6h18"/><path d="M4 12h12"/><path d="M4 18h6"/>',
}


def icon(name: str) -> Markup:
    return Markup(_WRAP.format(_PATHS.get(name, _PATHS["file"])))


def file_icon(content_type: str) -> Markup:
    """Map a MIME type to a file-type line icon."""
    ct = (content_type or "").lower()
    if ct.startswith("image/"):
        name = "image"
    elif ct.startswith("video/"):
        name = "video"
    elif ct.startswith("audio/"):
        name = "audio"
    elif any(k in ct for k in ("zip", "rar", "tar", "gzip", "7z", "compressed")):
        name = "archive"
    elif "sheet" in ct or "excel" in ct or "csv" in ct:
        name = "spreadsheet"
    elif (
        ct == "application/pdf"
        or ct.startswith("text/")
        or "word" in ct
        or "document" in ct
        or "presentation" in ct
        or "powerpoint" in ct
    ):
        name = "document"
    else:
        name = "file"
    return icon(name)
