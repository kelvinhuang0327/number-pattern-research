from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_report_header(
    *,
    title: str,
    mode: str,
    safety: str,
    purpose: str,
    scope: str,
    source: str,
    status: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    return {
        "title": title,
        "mode": mode,
        "safety": safety,
        "purpose": purpose,
        "scope": scope,
        "source": source,
        "status": status,
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def render_report_banner(header: dict[str, Any]) -> str:
    title = str(header.get("title", "REPORT"))
    mode = str(header.get("mode", "UNKNOWN"))
    safety = str(header.get("safety", "UNKNOWN"))
    purpose = str(header.get("purpose", ""))
    scope = str(header.get("scope", ""))
    status = str(header.get("status", ""))
    generated_at = str(header.get("generated_at", ""))
    return "\n".join([
        "=" * 72,
        title,
        f"MODE: {mode} | SAFETY: {safety}",
        f"PURPOSE: {purpose}",
        f"SCOPE: {scope}",
        f"STATUS: {status}",
        f"GENERATED_AT: {generated_at}",
        "=" * 72,
        "",
    ])


def render_section_block(title: str, lines: list[str], *, width: int = 72) -> str:
    divider = "━" * max(24, width)
    out = [
        "",
        divider,
        title,
        divider,
    ]
    out.extend(lines)
    return "\n".join(out)


def build_report_summary(
    *,
    mode: str,
    safety: str,
    scope: str,
    status: str,
    next_step: str,
    open_file: str,
    purpose: str | None = None,
) -> dict[str, Any]:
    return {
        "mode": mode,
        "safety": safety,
        "scope": scope,
        "status": status,
        "next_step": next_step,
        "open_file": open_file,
        "purpose": purpose or "",
    }


def render_report_summary(summary: dict[str, Any], *, width: int = 72) -> str:
    lines = [
        f"  Mode:         {summary.get('mode', 'UNKNOWN')}",
        f"  Safety:       {summary.get('safety', 'UNKNOWN')}",
        f"  Scope:        {summary.get('scope', 'n/a')}",
        f"  Status:       {summary.get('status', 'n/a')}",
        f"  Next Step:    {summary.get('next_step', 'n/a')}",
        f"  Open File:    {summary.get('open_file', 'n/a')}",
    ]
    purpose = str(summary.get("purpose", "")).strip()
    if purpose:
        lines.append(f"  Purpose:      {purpose}")
    return render_section_block("REPORT SUMMARY", lines, width=width)
