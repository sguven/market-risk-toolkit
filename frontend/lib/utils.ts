/** Tiny className joiner (avoids a clsx dependency). */
export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  // Dates are plain YYYY-MM-DD strings; parse as UTC and format in UTC so no timezone shift occurs.
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00Z` : iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" });
}

export function fmtNum(v: unknown, digits = 4): string {
  if (typeof v !== "number" || !Number.isFinite(v)) return String(v ?? "—");
  const abs = Math.abs(v);
  if (abs >= 1e6) return v.toLocaleString("en-US", { maximumFractionDigits: 0 });
  if (abs >= 1000) return v.toLocaleString("en-US", { maximumFractionDigits: 2 });
  return v.toLocaleString("en-US", { maximumFractionDigits: digits });
}

export function titleCase(s: string): string {
  return s.replace(/[_-]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
