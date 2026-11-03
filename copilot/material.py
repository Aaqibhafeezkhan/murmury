"""The material the copilot answers from: the files chosen before the call, turned into text.

PDF pages keep their page number, so an answer can point to it. Spreadsheets keep their cached
values (the numbers Excel last computed), sheet by sheet; hidden sheets are skipped.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Source:
    name: str
    kind: str  # "pdf", "xlsx", "text"
    text: str


def _pdf(path: Path) -> str:
    from pypdf import PdfReader

    pages = []
    for number, page in enumerate(PdfReader(path).pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append(f"[page {number}]\n{text}")
    return "\n\n".join(pages)


def _cell(value: object) -> str:
    if isinstance(value, float):
        return f"{value:,.4f}".rstrip("0").rstrip(".") if abs(value) < 10 else f"{value:,.0f}"
    return str(value)


def _xlsx(path: Path) -> str:
    from openpyxl import load_workbook

    book = load_workbook(path, data_only=True, read_only=False)
    sheets = []
    for sheet in book.worksheets:
        if sheet.sheet_state != "visible":
            continue
        rows = []
        for row in sheet.iter_rows():
            cells = [f"{c.coordinate}={_cell(c.value)}" for c in row if c.value not in (None, "")]
            if cells:
                rows.append(" | ".join(cells))
        if rows:
            sheets.append(f"[sheet {sheet.title}]\n" + "\n".join(rows))
    return "\n\n".join(sheets)


def load(paths: list[Path]) -> list[Source]:
    sources = []
    for path in paths:
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            sources.append(Source(path.name, "pdf", _pdf(path)))
        elif suffix in (".xlsx", ".xlsm"):
            sources.append(Source(path.name, "xlsx", _xlsx(path)))
        else:
            sources.append(Source(path.name, "text", path.read_text(encoding="utf-8")))
    return sources


def as_prompt(sources: list[Source]) -> str:
    """One stable block of text: same files in, same bytes out, so the prompt cache holds."""
    return "\n\n".join(f'<source name="{s.name}" kind="{s.kind}">\n{s.text}\n</source>' for s in sources)
