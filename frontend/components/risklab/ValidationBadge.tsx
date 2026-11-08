import type { ValidationLabel } from "@/lib/api";
import { Badge } from "@/components/ui/badge";

export const VALIDATION_META: Record<
  ValidationLabel,
  { label: string; tone: "neutral" | "info" | "warn" | "ok"; help: string }
> = {
  educational: {
    label: "Educational demonstration",
    tone: "neutral",
    help: "Illustrates a concept. Simplified inputs and assumptions; not a regulatory calculation.",
  },
  simplified: {
    label: "Simplified simulation",
    tone: "info",
    help: "Follows the regulatory logic in structure but omits parts of the full methodology. Not an official capital number.",
  },
  "partial-regulatory": {
    label: "Partial regulatory implementation",
    tone: "warn",
    help: "Implements the cited Basel provisions for the covered scope only; coverage gaps are listed with the result.",
  },
  "validated-regulatory": {
    label: "Validated regulatory calculation",
    tone: "ok",
    help: "Implements the cited provisions and reproduces documented reference examples in the validation record.",
  },
};

export function ValidationBadge({ label }: { label: ValidationLabel }) {
  const meta = VALIDATION_META[label] ?? VALIDATION_META.educational;
  return (
    <Badge tone={meta.tone} title={meta.help}>
      {meta.label}
    </Badge>
  );
}

export function SyntheticBadge() {
  return (
    <Badge tone="neutral" title="All market data on this page is generated or illustrative. No vendor or bank data.">
      Synthetic data
    </Badge>
  );
}
