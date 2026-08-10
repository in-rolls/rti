"""Shared helpers for the TN RTI scraper (Stage 1) and parser (Stage 2).

The site's ``show_sub_office.php`` links carry an encrypted ``min_code`` that is
**randomized on every request** -- the same office yields a different token each
time. So a token can be used to *fetch* a page once, but it is useless as an
identity. Identity is therefore content-based: an office is identified by the
normalized path of names from the root to it (e.g.
``ADI DRAVIDAR AND TRIBAL WELFARE DEPARTMENT > DIRECTORATE OF TRIBAL WELFARE, CHENNAI``).
"""

from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qs, unquote, urljoin, urlparse

from bs4 import BeautifulSoup

from ...config import scraper_data_dir

BASE = "https://rtionline.tn.gov.in"
ENTRY = f"{BASE}/displayPa.php"
INDEX = f"{BASE}/index.php"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
DATA = scraper_data_dir("tamil_nadu")
RAW = DATA / "raw"
MANIFEST = DATA / "manifest.jsonl"

ROOT_ID = "displayPa"
PATH_SEP = " > "
_LEAF_RE = re.compile(r"no\s+sub\s*offices", re.I)
_TITLE_PREFIXES = (
    "Onboarded HODs for ",
    "Onboarded HOD's for ",
    "Onboarded Sub Offices for ",
    "Onboarded Sub Office for ",
)


def clean(text: str) -> str:
    """Collapse all whitespace (incl. embedded newlines) to single spaces."""
    return re.sub(r"\s+", " ", text or "").strip()


def norm(name: str) -> str:
    """Normalized form used for identity/dedup (case- and whitespace-insensitive)."""
    return clean(name).upper()


def node_id_for(path_key: str) -> str:
    """Stable short id from a normalized root->node path key."""
    return hashlib.sha1(path_key.encode("utf-8")).hexdigest()[:16]


def link_token(href: str) -> str | None:
    """Percent-decoded min_code from a show_sub_office.php href (ephemeral handle)."""
    code = parse_qs(urlparse(href).query).get("min_code", [None])[0]
    return unquote(code) if code else None


def page_title_name(html: str) -> str:
    """The office a page belongs to, from its <h4> ('Onboarded ... for <NAME>')."""
    soup = BeautifulSoup(html, "lxml")
    h = soup.find("h4")
    text = h.get_text(" ", strip=True) if h else ""
    for pre in _TITLE_PREFIXES:
        if text.startswith(pre):
            return text[len(pre) :].strip()
    return text


def parse_rows(html: str, page_url: str = ENTRY) -> list[dict]:
    """Extract the office rows from a page.

    Each row -> {sl_no, name, address, token, url, is_leaf}. ``token``/``url`` are
    populated when the Action cell links to a child page; ``is_leaf`` is True when
    the cell instead reads 'No Suboffices Currently Onboarded'.
    """
    soup = BeautifulSoup(html, "lxml")
    rows: list[dict] = []
    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 3:
                continue
            sl_no = tds[0].get_text(" ", strip=True)
            if not sl_no.isdigit():  # skip header / spacer rows
                continue
            name_cell = tds[1]
            primary = name_cell.find("div", class_="text-primary")
            if primary is not None:
                name = primary.get_text(" ", strip=True)
                addr_div = primary.find_next_sibling("div")
                address = addr_div.get_text(" ", strip=True) if addr_div else ""
            else:  # root page: plain text, no address
                name = name_cell.get_text(" ", strip=True)
                address = ""
            action = tds[-1]
            link = action.find("a", href=re.compile("show_sub_office"))
            if link is not None:
                token = link_token(str(link["href"]))
                url = urljoin(page_url, str(link["href"]))
                is_leaf = False
            else:
                token, url = None, None
                is_leaf = bool(_LEAF_RE.search(action.get_text(" ", strip=True)))
            rows.append(
                {
                    "sl_no": int(sl_no),
                    "name": clean(name),
                    "address": clean(address),
                    "token": token,
                    "url": url,
                    "is_leaf": is_leaf,
                }
            )
    return rows
