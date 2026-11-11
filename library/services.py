import json
import re
import urllib.parse
import urllib.request

OPEN_LIBRARY_URL = "https://openlibrary.org/api/books"
TIMEOUT = 8


def clean_isbn(raw):
    return re.sub(r"[^0-9Xx]", "", raw or "").upper()


def lookup_isbn(raw):
    """ISBN'e göre kitap bilgisini döndürür; bulunamazsa None.
    Ağ hatalarında OSError/ValueError fırlatır."""
    isbn = clean_isbn(raw)
    if len(isbn) not in (10, 13):
        return None

    params = urllib.parse.urlencode(
        {"bibkeys": f"ISBN:{isbn}", "format": "json", "jscmd": "data"}
    )
    req = urllib.request.Request(
        f"{OPEN_LIBRARY_URL}?{params}",
        headers={"User-Agent": "kurum-kitaplik/0.1"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        data = json.load(resp)

    item = data.get(f"ISBN:{isbn}")
    if not item:
        return None

    title = item.get("title", "")
    if item.get("subtitle"):
        title = f"{title}: {item['subtitle']}"
    authors = ", ".join(a.get("name", "") for a in item.get("authors", []))
    publishers = item.get("publishers", [])
    cover = item.get("cover", {})
    return {
        "isbn": isbn,
        "title": title,
        "author": authors,
        "publisher": publishers[0].get("name", "") if publishers else "",
        "cover_url": cover.get("medium") or cover.get("small") or "",
    }