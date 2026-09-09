"""Parses raw HTML into clean, structured text (Docs/Ingestion-Architecture.md §3.2).

Groww's fund pages render their real data client-side from an embedded
__NEXT_DATA__ JSON blob (a Next.js SSR payload) — the visible HTML text is
mostly site navigation/marketing chrome, not the fund facts. So for Groww
pages, we extract the structured JSON fields directly (accurate, no nav-menu
contamination) and render them as plain text, then hand that text to the
*same* generic fixed-size chunker used for everything else (per the confirmed
2026-09-06 chunking strategy) — this is a parsing correctness fix, not a
reopening of that chunking-strategy decision.

Non-Groww sources (future AMFI/SEBI/AMC prose pages) fall back to generic
HTML text extraction with boilerplate stripping and table linearization.
"""
import json
import re

from bs4 import BeautifulSoup

STRIP_TAGS = ["script", "style", "nav", "footer", "header", "svg", "noscript", "iframe"]
HEADING_TAGS = {"h1", "h2", "h3", "h4"}
BLOCK_TAGS = {"p", "div", "li", "section", "article", "tr"}

_NEXT_DATA_RE = re.compile(
    r'__NEXT_DATA__"\s+type="application/json"[^>]*>(.*?)</script>', re.S
)


# --- Groww JSON-based extraction -------------------------------------------------


def _extract_next_data(raw_html: str) -> dict | None:
    match = _NEXT_DATA_RE.search(raw_html)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def _fmt_currency(value) -> str | None:
    if value is None:
        return None
    return f"₹{value:,.2f}" if isinstance(value, float) else f"₹{value:,}"


def _fmt_lock_in(lock_in: dict | None) -> str:
    if not lock_in:
        return "No lock-in period."
    parts = [f"{lock_in[unit]} {unit}" for unit in ("years", "months", "days") if lock_in.get(unit)]
    return f"Lock-in period: {', '.join(parts)}." if parts else "No lock-in period."


def _block(text: str, section_hint: str) -> dict:
    return {"text": text, "section_hint": section_hint}


def _render_groww_fields(mf: dict) -> list[dict]:
    blocks = []

    scheme_name = mf.get("scheme_name") or ""
    fund_house = mf.get("fund_house") or ""
    category = mf.get("category") or ""
    sub_category = mf.get("sub_category") or ""
    blocks.append(
        _block(
            f"{scheme_name} is managed by {fund_house}. "
            f"Category: {category} - {sub_category}. "
            f"Launch date: {mf.get('launch_date', 'not available')}. "
            f"Fund manager: {mf.get('fund_manager', 'not available')}. "
            f"{mf.get('description', '')}".strip(),
            "Fund Overview",
        )
    )

    expense_ratio = mf.get("expense_ratio")
    blocks.append(
        _block(
            f"Expense ratio: {expense_ratio}%. "
            f"Base expense ratio: {mf.get('base_expense_ratio', 'not available')}%. "
            f"Exit load: {mf.get('exit_load', 'not available')}.",
            "Costs & Charges",
        )
    )

    blocks.append(
        _block(
            f"Minimum investment amount: {_fmt_currency(mf.get('min_investment_amount'))}. "
            f"Minimum SIP investment: {_fmt_currency(mf.get('min_sip_investment'))}. "
            f"Minimum additional investment: {_fmt_currency(mf.get('mini_additional_investment'))}. "
            f"SIP allowed: {'Yes' if mf.get('sip_allowed') else 'No'}. "
            f"Lumpsum allowed: {'Yes' if mf.get('lumpsum_allowed') else 'No'}.",
            "Investment Limits",
        )
    )

    blocks.append(
        _block(
            f"Riskometer classification: {mf.get('nfo_risk', 'not available')}. "
            f"Benchmark: {mf.get('benchmark', 'not available')} "
            f"({mf.get('benchmark_name', 'not available')}). "
            f"{_fmt_lock_in(mf.get('lock_in'))}",
            "Risk & Benchmark",
        )
    )

    aum = mf.get("aum")
    aum_text = f"{aum:,.2f} Cr" if isinstance(aum, (int, float)) else "not available"
    blocks.append(
        _block(
            f"NAV: {_fmt_currency(mf.get('nav'))} as of {mf.get('nav_date', 'not available')}. "
            f"AUM: {aum_text}. "
            f"ISIN: {mf.get('isin', 'not available')}.",
            "Fund Facts",
        )
    )

    sid_url = mf.get("sid_url")
    if sid_url:
        blocks.append(
            _block(f"Scheme Information Document (SID) is available at: {sid_url}", "Official Documents")
        )

    return [b for b in blocks if b["text"].strip()]


# --- Generic HTML text extraction (fallback for non-Groww/JSON sources) --------


def _linearize_table(table_tag) -> str:
    rows_text = []
    header_cells = table_tag.find("tr")
    headers = [th.get_text(strip=True) for th in header_cells.find_all(["th", "td"])] if header_cells else []

    for row in table_tag.find_all("tr"):
        cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
        if not cells or all(not c for c in cells):
            continue
        if headers and len(cells) == len(headers):
            pairs = [f"{h}={v}" for h, v in zip(headers, cells) if h]
            rows_text.append(", ".join(pairs) if pairs else " ".join(cells))
        else:
            rows_text.append(" | ".join(cells))
    return "\n".join(rows_text)


def _parse_generic_html(raw_html: str) -> list[dict]:
    soup = BeautifulSoup(raw_html, "lxml")

    for tag_name in STRIP_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    for table in soup.find_all("table"):
        table.replace_with(soup.new_string(_linearize_table(table)))

    blocks: list[dict] = []
    current_section = None
    all_container_tags = HEADING_TAGS | BLOCK_TAGS

    body = soup.body or soup
    for element in body.find_all(list(all_container_tags)):
        if element.find(list(all_container_tags)) is not None:
            continue

        if element.name in HEADING_TAGS:
            heading_text = element.get_text(strip=True)
            if heading_text:
                current_section = heading_text
            continue

        text = " ".join(element.get_text(separator=" ", strip=True).split())
        if not text:
            continue
        blocks.append(_block(text, current_section))

    return blocks


# --- Entry point -----------------------------------------------------------------


def parse(raw_html: str) -> list[dict]:
    """Returns a list of {"text": str, "section_hint": str | None} blocks in order."""
    next_data = _extract_next_data(raw_html)
    if next_data:
        mf = next_data.get("props", {}).get("pageProps", {}).get("mfServerSideData")
        if mf:
            return _render_groww_fields(mf)

    return _parse_generic_html(raw_html)
