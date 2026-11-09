"""Small console-table helpers so examples read like desk reports."""

from __future__ import annotations

from typing import Iterable, Sequence


def fmt_money(x: float) -> str:
    sign = "-" if x < 0 else ""
    return f"{sign}${abs(x):,.2f}"


def table(headers: Sequence[str], rows: Iterable[Sequence], floatfmt: str = "{:,.4f}") -> str:
    rows = [[(floatfmt.format(c) if isinstance(c, float) else str(c)) for c in r] for r in rows]
    widths = [max(len(str(h)), *(len(r[i]) for r in rows)) if rows else len(str(h)) for i, h in enumerate(headers)]
    line = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    out = [line, "| " + " | ".join(str(h).ljust(w) for h, w in zip(headers, widths)) + " |", line]
    for r in rows:
        out.append("| " + " | ".join(c.rjust(w) if _is_num(c) else c.ljust(w) for c, w in zip(r, widths)) + " |")
    out.append(line)
    return "\n".join(out)


def _is_num(s: str) -> bool:
    try:
        float(s.replace(",", "").replace("$", "").replace("%", ""))
        return True
    except ValueError:
        return False


def banner(title: str) -> str:
    bar = "=" * max(72, len(title) + 4)
    return f"\n{bar}\n  {title}\n{bar}"
