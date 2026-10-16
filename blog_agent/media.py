import json
import re
import ssl
from typing import Literal, TypedDict
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def _build_ssl_context() -> ssl.SSLContext:
    """Return an SSL context pinned to the certifi CA bundle.

    The Windows certificate store can hold expired copies of trusted roots
    (for example an expired ISRG Root X2), which makes Python reject otherwise
    valid server chains with "certificate has expired". Using the certifi
    bundle avoids depending on the local system stores. Falls back to the
    default context when certifi is unavailable.
    """
    try:
        import certifi
    except ImportError:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


_SSL_CONTEXT = _build_ssl_context()


class CommonsMedia(TypedDict):
    title: str
    url: str
    thumbnail_url: str
    description_url: str
    mime: str


def search_commons_media(
    query: str,
    media_type: Literal["image", "video"],
) -> list[CommonsMedia]:
    filetype = {"image": "bitmap", "video": "video"}[media_type]
    params = urlencode(
        {
            "action": "query",
            "generator": "search",
            "gsrnamespace": 6,
            "gsrlimit": 30,
            "gsrsearch": f"{query} filetype:{filetype}",
            "prop": "imageinfo",
            "iiprop": "url|mime|mediatype",
            "iiurlwidth": 600,
            "format": "json",
        }
    )
    request = Request(
        f"https://commons.wikimedia.org/w/api.php?{params}",
        headers={"User-Agent": "TechnicalBlogAgent/1.0 (Wikimedia Commons media search)"},
    )
    with urlopen(request, timeout=12, context=_SSL_CONTEXT) as response:
        payload = json.load(response)

    if not isinstance(payload, dict):
        raise ValueError("Wikimedia Commons a retourné une réponse invalide.")
    if "error" in payload:
        error = payload["error"]
        message = (
            error.get("info", "erreur inconnue")
            if isinstance(error, dict)
            else str(error)
        )
        raise ValueError(f"Erreur de l’API Wikimedia Commons : {message}")

    query_data = payload.get("query")
    pages = query_data.get("pages", {}) if isinstance(query_data, dict) else None
    if not isinstance(pages, dict):
        raise ValueError("Wikimedia Commons a retourné une liste de médias invalide.")

    expected_mediatype = {"image": "BITMAP", "video": "VIDEO"}[media_type]
    media: list[CommonsMedia] = []
    if not all(isinstance(page, dict) for page in pages.values()):
        raise ValueError("Wikimedia Commons a retourné un fichier média invalide.")
    for page in sorted(pages.values(), key=lambda item: item.get("index", 0)):
        imageinfo = page.get("imageinfo", [])
        if not imageinfo:
            continue
        info = imageinfo[0]
        if not isinstance(info, dict):
            raise ValueError("Wikimedia Commons a retourné les détails d’un média invalides.")
        if info.get("mediatype") != expected_mediatype:
            continue
        if media_type == "video" and info.get("mime") not in {"video/webm", "video/mp4"}:
            continue
        url = info.get("url", "")
        description_url = info.get("descriptionurl", "")
        thumbnail_url = info.get("thumburl", "")
        title = page.get("title", "Fichier Commons")
        if not (
            isinstance(url, str)
            and url.startswith("https://upload.wikimedia.org/")
            and isinstance(description_url, str)
            and description_url.startswith("https://commons.wikimedia.org/")
            and isinstance(title, str)
        ):
            continue
        if media_type == "image" and not thumbnail_url.startswith(
            "https://thumb.wikimedia.org/"
        ):
            continue
        media.append(
            {
                "title": title.removeprefix("File:"),
                "url": url,
                "thumbnail_url": thumbnail_url,
                "description_url": description_url,
                "mime": info.get("mime", ""),
            }
        )
    return media


SECTION_SEARCH_LIMIT = 6
IMAGES_PER_SECTION = 3
INTRODUCTION_HEADING = "Introduction"
_GENERIC_SECTION_HEADINGS = {
    "introduction",
    "intro",
    "conclusion",
    "conclusion générale",
    "conclusion generale",
    "remerciements",
}
_LINK_PATTERN = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")


class ArticleSectionMedia(TypedDict):
    heading: str
    query: str
    paragraph: str
    images: list[CommonsMedia]
    links: dict[str, str]
    error: str | None


def _clean_paragraph(line: str) -> str:
    text = _LINK_PATTERN.sub(r"\1", line.strip())
    if len(text) > 200:
        text = f"{text[:200]}…"
    return text


def parse_article_sections(article: str) -> list[dict[str, str]]:
    """Split a Markdown article into H2 sections with a paragraph excerpt.

    The text before the first H2 heading becomes the Introduction section.
    """
    sections: list[dict[str, str]] = []
    current = {"heading": INTRODUCTION_HEADING, "paragraph": ""}
    in_code_block = False
    for line in article.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        heading_match = re.match(r"^##\s+(.+)$", stripped)
        if heading_match:
            sections.append(current)
            current = {"heading": heading_match.group(1).strip(), "paragraph": ""}
            continue
        if (
            not current["paragraph"]
            and stripped
            and not stripped.startswith(("#", "-", "*", "+"))
            and not re.match(r"^\d+\.", stripped)
        ):
            current["paragraph"] = _clean_paragraph(stripped)
    sections.append(current)
    return sections


def build_search_links(query: str) -> dict[str, str]:
    """Build pre-filled search links for a section query."""
    return {
        "youtube": (
            f"https://www.youtube.com/results?{urlencode({'search_query': query})}"
        ),
        "google_images": (
            f"https://www.google.com/search?{urlencode({'tbm': 'isch', 'q': query})}"
        ),
        "commons": (
            "https://commons.wikimedia.org/wiki/Special:MediaSearch?"
            f"{urlencode({'search': query, 'type': 'image'})}"
        ),
    }


def collect_article_media(article: str, topic: str) -> list[ArticleSectionMedia]:
    """Search Commons images and build search links for each article section.

    A section whose heading is generic (Introduction, Conclusion, …) reuses the
    topic alone as its query. Commons failures are recorded per section so the
    search links stay available as a fallback.
    """
    if not article.strip():
        return []
    media_by_section: list[ArticleSectionMedia] = []
    for section in parse_article_sections(article)[:SECTION_SEARCH_LIMIT]:
        heading = section["heading"]
        if heading.casefold() in _GENERIC_SECTION_HEADINGS:
            query = topic
        else:
            query = " ".join(part for part in (topic, heading) if part).strip()
        images: list[CommonsMedia] = []
        error: str | None = None
        try:
            images = search_commons_media(query, "image")[:IMAGES_PER_SECTION]
        except (URLError, TimeoutError, json.JSONDecodeError, ValueError) as search_error:
            error = str(search_error)
        media_by_section.append(
            {
                "heading": heading,
                "query": query,
                "paragraph": section["paragraph"],
                "images": images,
                "links": build_search_links(query),
                "error": error,
            }
        )
    return media_by_section
