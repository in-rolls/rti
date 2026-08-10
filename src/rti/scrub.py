"""Derive a publishable copy of the data, and refuse to let the real copy escape.

Two jobs. `public_rows` turns real rows into redacted ones, which is what
`tables.write_table` calls so the committed CSVs are never the true ones.
`scan_tracked` reads back over everything git is tracking and fails if personal
data got in anyway.

The redaction rule throughout is **replace the value, keep the fact**. Blanking
`evidence_url` would make the public data assert that no evidence was captured,
which is false and worse than saying nothing at all. So an empty field stays
empty and a populated one becomes a token.

The guard is not only a set of patterns. Patterns catch an email address or a
phone number; they do not catch "spoke to Ramesh at the counter". So it also
searches for every real value in the pseudonym map, which means it knows the
names it is looking for.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

from .config import private_config_dir, pseudonyms_path, repo_root

# --------------------------------------------------------------------------
# Column rules
# --------------------------------------------------------------------------

PSEUDONYM_COLUMNS = frozenset({"filed_by", "recorded_by", "applicant", "coder_id"})
EMAIL_COLUMNS = frozenset({"sender_email", "email"})
DOCUMENT_COLUMNS = frozenset(
    {"evidence_url", "screen_recording_url", "document_url", "receipt_url"}
)
OPAQUE_COLUMNS = frozenset({"payment_reference"})
WITHHELD_COLUMNS = frozenset({"notes", "verify_note"})

DOCUMENT_TOKEN = "[document recorded]"
OPAQUE_TOKEN = "[redacted]"
WITHHELD_TOKEN = "[notes withheld]"
EMAIL_DOMAIN = "redacted.invalid"

# --------------------------------------------------------------------------
# Patterns
# --------------------------------------------------------------------------

EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")

# Indian mobile numbers are ten digits starting 6-9, written with or without
# +91 and with assorted spacing. Landlines only appear after a label, so they
# are matched by the label rather than by shape.
#
# The alphanumeric lookaround is load-bearing. `authority_id` is twelve hex
# characters, and roughly one in a hundred begins with ten digits that look
# exactly like a mobile number. Requiring a non-alphanumeric on both sides
# rejects `7163813153ab` while keeping `PIO 9800000123 / ...`.
#
# The country code must carry a `+` or a separator for the same reason: a bare
# `91` followed by ten digits is indistinguishable from a twelve-digit id.
PHONE_RE = re.compile(
    r"(?<![0-9A-Za-z])(?:\+91[\s-]?|91[\s-])?[6-9]\d{4}[\s-]?\d{5}(?![0-9A-Za-z])"
    r"|(?:phone|tel|mob|mobile|contact)[\s.:-]*\+?\d[\d\s-]{5,13}\d",
    re.I,
)

DOCUMENT_URL_RE = re.compile(
    r"https?://(?:drive|docs)\.google\.com/\S+" r"|https?://\S*\.(?:sharepoint|dropbox)\.com/\S+",
    re.I,
)

NAME_TOKEN = "[name withheld]"


def name_pattern(name: str) -> re.Pattern[str]:
    """Match a name as a whole word, case-insensitively.

    Used by both the scrubber and the guard, so the guard never flags something
    the scrubber deliberately leaves alone. Boundaries matter: `vasanthi` must
    not match inside `vasanthipuram`, a town in Tirupur.
    """
    return re.compile(rf"\b{re.escape(name)}\b", re.I)


# Names in scraped addresses are matched literally, not by pattern.
#
# An honorific regex was tried first and abandoned. Across 17,417 Tamil Nadu
# addresses it produced 34 matches, of which one was a person. The rest were
# institutions: `Dr. M.G.R. University`, `Sri Ramakrishna Mission`,
# `Dr. A.P.J. Abdul Kalam`, and `Thiru.Vi.Ka Industrial Estate`, which is a
# place in Chennai named after a writer. Indian institutions are overwhelmingly
# named after people, so an honorific marks a building far more often than a
# resident officer, and scrubbing on it corrupts real postal addresses. It also
# missed the surname of the one real person it did find.
#
# The literal list lives in the private config, because writing down the names
# you want removed is not something you can do in a committed file.


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    kind: str
    excerpt: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.kind}: {self.excerpt}"


# --------------------------------------------------------------------------
# Pseudonyms
# --------------------------------------------------------------------------


class Pseudonyms:
    """A small, readable, gitignored map from a real person to a stable label.

    A map rather than a hash: `RA-01` tells a reader that two rows are the same
    filer, which is the only thing the public data needs the name for, and it
    stays auditable at this scale. It is also the guard's list of what to hunt
    for in tracked files.
    """

    def __init__(self, people: dict[str, str] | None = None, redact: list[str] | None = None):
        self.people: dict[str, str] = dict(people or {})
        self.redact: list[str] = list(redact or [])

    @classmethod
    def load(cls, path: Path | None = None) -> "Pseudonyms":
        path = path or pseudonyms_path()
        if not path.is_file():
            return cls()
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return cls(raw.get("people") or {}, raw.get("redact") or [])

    def save(self, path: Path | None = None) -> Path:
        path = path or pseudonyms_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        body = (
            "# Real identities, and the labels that stand in for them publicly.\n"
            "# Gitignored: this file is the only way back from a pseudonym, and it\n"
            "# is also the list `rti-scrub --check` searches tracked files for.\n"
            "#\n"
            "# people:  study participants. Extended automatically when a new name\n"
            "#          first appears; a label is safe to rename by hand.\n"
            "# redact:  literal strings removed from any published free text, for\n"
            "#          third parties who are named in scraped records. Add by hand.\n\n"
        )
        path.write_text(
            body
            + yaml.safe_dump({"people": self.people, "redact": self.redact}, allow_unicode=True),
            encoding="utf-8",
        )
        return path

    @staticmethod
    def _key(value: str) -> str:
        return " ".join((value or "").strip().lower().split())

    def label(self, value: str) -> str:
        """The label for a person, minting a new one the first time they appear.

        A value that is already a label passes through unchanged. Without that,
        redacting an already-public row would treat `RA-01` as a new person and
        mint `RA-02` for them, which is exactly what happens on a clone that has
        no private tables and re-writes the public ones.
        """
        key = self._key(value)
        if not key:
            return ""
        if key in self.people:
            return self.people[key]
        if value.strip() in set(self.people.values()):
            return value.strip()
        self.people[key] = f"RA-{len(set(self.people.values())) + 1:02d}"
        return self.people[key]

    def email(self, value: str) -> str:
        """An address that cannot be delivered to, tied to the same person."""
        if value.strip().lower().endswith(f"@{EMAIL_DOMAIN}"):
            return value.strip().lower()
        label = self.label(value)
        return f"{label.lower()}@{EMAIL_DOMAIN}" if label else ""

    def real_values(self) -> list[str]:
        """Every real string the guard should hunt for, longest first."""
        values = set(self.people) | {self._key(name) for name in self.redact}
        return sorted((v for v in values if v), key=len, reverse=True)


# --------------------------------------------------------------------------
# Redaction
# --------------------------------------------------------------------------


def scrub_text(text: str) -> str:
    """Remove contact details from free text, leaving the rest readable."""
    if not text:
        return text
    text = DOCUMENT_URL_RE.sub("[document]", text)
    text = EMAIL_RE.sub("[email]", text)
    return PHONE_RE.sub("[phone]", text)


def scrub_person_names(text: str, names: list[str] | None = None) -> str:
    """Remove named individuals from scraped office addresses.

    Applied to the TN universe's `address` column, where an office record
    occasionally names the officer sitting in it. Institutional addresses,
    office emails, and PIN codes are left alone: they are the office rather
    than a person, and postal filing needs them.

    `names` defaults to the `redact` list in the private config. Adding a name
    there and re-running `rti-categorize-tn` removes it from the published file.
    """
    if not text:
        return text
    if names is None:
        names = Pseudonyms.load().redact
    for name in sorted(names, key=len, reverse=True):
        if name:
            text = name_pattern(name).sub(NAME_TOKEN, text)
    return text


def redact_value(column: str, value: object, pseudonyms: Pseudonyms) -> str:
    """One column's public value. Empty in, empty out, always.

    Values arrive as whatever the caller holds: `relevant` is an int in memory
    and a string once it has been through a CSV.
    """
    value = "" if value is None else str(value).strip()
    if not value:
        return ""
    if column in PSEUDONYM_COLUMNS:
        return pseudonyms.label(value)
    if column in EMAIL_COLUMNS:
        return pseudonyms.email(value)
    if column in DOCUMENT_COLUMNS:
        return DOCUMENT_TOKEN
    if column in OPAQUE_COLUMNS:
        return OPAQUE_TOKEN
    if column in WITHHELD_COLUMNS:
        return WITHHELD_TOKEN
    return value


def redact_row(row: dict, pseudonyms: Pseudonyms) -> dict:
    return {column: redact_value(column, value, pseudonyms) for column, value in row.items()}


def public_rows(rows: list[dict], pseudonyms: Pseudonyms | None = None) -> list[dict]:
    """The publishable form of a table, extending the map with anyone new."""
    pseudonyms = Pseudonyms.load() if pseudonyms is None else pseudonyms
    before = dict(pseudonyms.people)
    out = [redact_row(row, pseudonyms) for row in rows]
    if pseudonyms.people != before:
        pseudonyms.save()
    return out


# --------------------------------------------------------------------------
# The guard
# --------------------------------------------------------------------------

SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".pdf", ".db", ".ico", ".gz", ".zip"}

# This module defines the patterns, so it necessarily contains examples of them.
ALLOWED_PATHS = {"src/rti/scrub.py"}

# Test fixtures have to contain personal-data-shaped strings, since that is what
# they test the guard against. They are checked for real names, which the
# pseudonym map knows, but not for the shapes.
ALLOWED_PREFIXES = ("tests/",)

# Offices scraped from a public government portal. The decision is to publish
# institutional contact details, which postal filing needs, and to strip named
# individuals; `scrub_person_names` does the stripping at write time, and the
# name check below still applies here.
INSTITUTIONAL_PREFIXES = ("data/scrapers/",)

ALLOWED_EMAIL_DOMAINS = ("example.org", "example.com", "redacted.invalid")


def _is_allowed_email(value: str) -> bool:
    return value.lower().endswith(ALLOWED_EMAIL_DOMAINS)


def tracked_files(root: Path | None = None) -> list[Path]:
    root = root or repo_root()
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return [root / name for name in result.stdout.split("\0") if name]


def scan_file(path: Path, root: Path, real_values: list[str]) -> list[Finding]:
    relative = path.relative_to(root).as_posix()
    if relative in ALLOWED_PATHS or path.suffix.lower() in SKIP_SUFFIXES:
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, FileNotFoundError):
        return []

    # A known real name is never acceptable, wherever it appears.
    names_only = relative.startswith(ALLOWED_PREFIXES) or relative.startswith(
        INSTITUTIONAL_PREFIXES
    )

    patterns = [(real, name_pattern(real)) for real in real_values]
    findings = []
    for number, line in enumerate(text.splitlines(), 1):
        for real, pattern in patterns:
            if pattern.search(line):
                findings.append(Finding(relative, number, "name", real))
        if names_only:
            continue
        for match in EMAIL_RE.findall(line):
            if not _is_allowed_email(match):
                findings.append(Finding(relative, number, "email", match))
        for match in DOCUMENT_URL_RE.findall(line):
            findings.append(Finding(relative, number, "document url", match[:60]))
        for match in PHONE_RE.findall(line):
            findings.append(Finding(relative, number, "phone", match.strip()[:40]))
    return findings


def scan_tracked(root: Path | None = None) -> list[Finding]:
    """Every piece of personal data git is currently tracking."""
    root = root or repo_root()
    real_values = Pseudonyms.load().real_values()
    findings: list[Finding] = []
    for path in tracked_files(root):
        if path.is_file():
            findings.extend(scan_file(path, root, real_values))
    return findings


def rebuild_public_tables() -> dict[str, int]:
    """Re-derive every public table from its private original."""
    from .tables import TABLES, read_table, write_table

    counts = {}
    for name in TABLES:
        rows = read_table(name)
        write_table(name, rows)
        counts[name] = len(rows)
    return counts


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(
        description="Derive the public tables, or check that nothing personal is tracked."
    )
    ap.add_argument(
        "--check",
        action="store_true",
        help="scan tracked files for personal data and fail if any is found",
    )
    args = ap.parse_args(argv)

    if not args.check:
        counts = rebuild_public_tables()
        for name, n in counts.items():
            print(f"  {name}: {n} rows -> data/tables/{name}.csv")
        people = Pseudonyms.load().people
        print(f"pseudonyms: {len(set(people.values()))} in {pseudonyms_path()}")
        return

    findings = scan_tracked()
    if not findings:
        print("no personal data in tracked files")
        return

    print(f"{len(findings)} finding(s) in tracked files:\n", file=sys.stderr)
    for finding in findings:
        print(f"  {finding}", file=sys.stderr)
    print(
        "\nThese files are tracked by git and would be published on push.\n"
        f"Real data belongs under data/private/ and {private_config_dir()},\n"
        "both of which are gitignored. Run `rti-scrub` to re-derive the public\n"
        "tables, or move the file.",
        file=sys.stderr,
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
