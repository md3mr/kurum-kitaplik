import json
import os
import re
import time
import urllib.parse
import urllib.request

OPEN_LIBRARY_URL = "https://openlibrary.org/api/books"
GOOGLE_BOOKS_URL = "https://www.googleapis.com/books/v1/volumes"
TIMEOUT = 8
ATTEMPTS = 2


class InvalidISBN(Exception):
    """ISBN biçimi ya da kontrol hanesi hatalı."""


def clean_isbn(raw):
    return re.sub(r"[^0-9Xx]", "", raw or "").upper()


def _valid13(s):
    if not re.fullmatch(r"\d{13}", s):
        return False
    total = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(s))
    return total % 10 == 0


def _valid10(s):
    if not re.fullmatch(r"\d{9}[\dX]", s):
        return False
    total = sum((10 if c == "X" else int(c)) * (10 - i) for i, c in enumerate(s))
    return total % 11 == 0


def _to13(isbn10):
    core = "978" + isbn10[:9]
    check = (10 - sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(core)) % 10) % 10
    return core + str(check)


def _to10(isbn13):
    core = isbn13[3:12]
    check = (11 - sum(int(c) * (10 - i) for i, c in enumerate(core)) % 11) % 11
    return core + ("X" if check == 10 else str(check))


def candidates(raw):
    """Geçerli ISBN için denenecek biçimler (önce 13 haneli). Hatalıysa InvalidISBN."""
    isbn = clean_isbn(raw)
    if len(isbn) == 13 and _valid13(isbn):
        out = [isbn]
        if isbn.startswith("978"):
            out.append(_to10(isbn))
        return out
    if len(isbn) == 10 and _valid10(isbn):
        return [_to13(isbn), isbn]
    raise InvalidISBN(isbn)


def _get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "kurum-kitaplik/0.1"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.load(resp)


def _open_library(cands):
    bibkeys = ",".join(f"ISBN:{c}" for c in cands)
    params = urllib.parse.urlencode({"bibkeys": bibkeys, "format": "json", "jscmd": "data"})
    data = _get_json(f"{OPEN_LIBRARY_URL}?{params}")
    for c in cands:
        item = data.get(f"ISBN:{c}")
        if item:
            title = item.get("title", "")
            if item.get("subtitle"):
                title = f"{title}: {item['subtitle']}"
            publishers = item.get("publishers", [])
            cover = item.get("cover", {})
            return {
                "title": title,
                "author": ", ".join(a.get("name", "") for a in item.get("authors", [])),
                "publisher": publishers[0].get("name", "") if publishers else "",
                "cover_url": cover.get("medium") or cover.get("small") or "",
            }
    return None


def _google_books(cands):
    key = os.environ.get("GOOGLE_BOOKS_API_KEY", "")
    for c in cands:
        q = {"q": f"isbn:{c}"}
        if key:
            q["key"] = key
        data = _get_json(f"{GOOGLE_BOOKS_URL}?{urllib.parse.urlencode(q)}")
        items = data.get("items") or []
        if items:
            info = items[0].get("volumeInfo", {})
            title = info.get("title", "")
            if info.get("subtitle"):
                title = f"{title}: {info['subtitle']}"
            links = info.get("imageLinks", {})
            cover = links.get("thumbnail") or links.get("smallThumbnail") or ""
            return {
                "title": title,
                "author": ", ".join(info.get("authors", [])),
                "publisher": info.get("publisher", ""),
                "cover_url": cover.replace("http://", "https://"),
            }
    return None


def lookup_isbn(raw):
    """Kitap bilgisini döndürür; bulunamazsa None.
    ISBN hatalıysa InvalidISBN, tüm kaynaklara ulaşılamazsa OSError/ValueError fırlatır."""
    cands = candidates(raw)
    errors = []
    answered = False  # en az bir kaynak hatasız "yok" ya da "var" dedi mi

    for source in (_open_library, _google_books):
        for attempt in range(ATTEMPTS):
            try:
                result = source(cands)
            except (OSError, ValueError) as exc:
                errors.append(exc)
                if attempt < ATTEMPTS - 1:
                    time.sleep(0.7)
                continue
            answered = True
            if result:
                result["isbn"] = cands[0]
                return result
            break

    if not answered and errors:
        raise errors[-1]
    return None