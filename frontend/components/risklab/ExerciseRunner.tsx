"use client";
import * as React from "react";
import { Play, RotateCcw, AlertTriangle } from "lucide-react";
import { api, type CalcSummary, type CalcResponse, type JsonSchema, type JsonSchemaProperty } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input, Label, Select } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import { Badge } from "@/components/ui/badge";
import { KpiTile } from "./KpiTile";
import { ValidationBadge, SyntheticBadge } from "./ValidationBadge";
import { CalcTrace } from "./CalcTrace";
import { ChartHistogram } from "./ChartHistogram";
import { Markdown } from "./Markdown";
import { fmtNum, titleCase } from "@/lib/utils";

type Inputs = Record<string, unknown>;

/* ------------------------------------------------------------------ */
/* Schema helpers                                                      */
/* ------------------------------------------------------------------ */

function resolveRef(schema: JsonSchema, p: JsonSchemaProperty): JsonSchemaProperty {
  if (p.$ref) {
    const name = p.$ref.split("/").pop() ?? "";
    return schema.$defs?.[name] ?? p;
  }
  if (p.anyOf) {
    // Pydantic Optional[X] -> anyOf [X, null]; take the first non-null branch.
    const branch = p.anyOf.find((b) => b.type !== "null") ?? p.anyOf[0];
    return { ...p, ...resolveRef(schema, branch), anyOf: undefined };
  }
  return p;
}

function kindOf(p: JsonSchemaProperty): "integer" | "number" | "boolean" | "enum" | "object" | "string" {
  if (p.enum) return "enum";
  const t = Array.isArray(p.type) ? p.type.find((x) => x !== "null") : p.type;
  if (t === "integer") return "integer";
  if (t === "number") return "number";
  if (t === "boolean") return "boolean";
  if (t === "object") return "object";
  return "string";
}

/** Choose a slider range when the schema gives bounds; otherwise infer from the default. */
function sliderRange(p: JsonSchemaProperty, value: number, isInt: boolean) {
  const min = p.minimum ?? (p.exclusiveMinimum !== undefined ? p.exclusiveMinimum : undefined);
  const max = p.maximum ?? (p.exclusiveMaximum !== undefined ? p.exclusiveMaximum : undefined);
  if (min !== undefined && max !== undefined) {
    const step = isInt ? Math.max(1, Math.round((max - min) / 200)) : (max - min) / 200;
    return { min, max, step };
  }
  return null;
}

/* ------------------------------------------------------------------ */
/* Field editors                                                       */
/* ------------------------------------------------------------------ */

function NumberField({
  name,
  prop,
  value,
  onChange,
}: {
  name: string;
  prop: JsonSchemaProperty;
  value: number;
  onChange: (v: number) => void;
}) {
  const isInt = kindOf(prop) === "integer";
  const range = sliderRange(prop, value, isInt);
  const step = isInt ? 1 : Math.abs(value) >= 100 ? 1 : Math.abs(value) >= 1 ? 0.01 : 0.001;
  return (
    <div>
      <Label htmlFor={`f-${name}`} title={prop.description}>
        {prop.title ?? titleCase(name)}
        {range ? <span className="text-faint ml-1 tnum">({fmtNum(range.min)}–{fmtNum(range.max)})</span> : null}
      </Label>
      <div className="flex items-center gap-3">
        {range ? (
          <Slider
            value={value}
            min={range.min}
            max={range.max}
            step={range.step}
            onChange={onChange}
            aria-label={name}
            className="flex-1"
          />
        ) : null}
        <Input
          id={`f-${name}`}
          type="number"
          step={step}
          value={Number.isFinite(value) ? value : ""}
          onChange={(e) => onChange(e.target.value === "" ? NaN : Number(e.target.value))}
          className={range ? "w-28" : "w-full"}
        />
      </div>
      {prop.description ? <div className="text-[11px] text-faint mt-1">{prop.description}</div> : null}
    </div>
  );
}

function ObjectField({
  name,
  prop,
  value,
  onChange,
}: {
  name: string;
  prop: JsonSchemaProperty;
  value: Record<string, number>;
  onChange: (v: Record<string, number>) => void;
}) {
  const [newKey, setNewKey] = React.useState("");
  const entries = Object.entries(value ?? {});
  return (
    <div className="md:col-span-2">
      <Label title={prop.description}>{prop.title ?? titleCase(name)}</Label>
      <div className="border border-border rounded-[var(--rl-radius)] divide-y divide-border">
        {entries.map(([k, v]) => (
          <div key={k} className="flex items-center gap-2 px-2 py-1.5">
            <span className="font-mono text-xs w-20">{k}</span>
            <Input
              type="number"
              value={v}
              onChange={(e) => onChange({ ...value, [k]: Number(e.target.value) })}
              className="h-8"
            />
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                const next = { ...value };
                delete next[k];
                onChange(next);
              }}
              aria-label={`Remove ${k}`}
            >
              ×
            </Button>
          </div>
        ))}
        <div className="flex items-center gap-2 px-2 py-1.5">
          <Input
            placeholder="Add key (e.g. GBP)"
            value={newKey}
            onChange={(e) => setNewKey(e.target.value.toUpperCase())}
            className="h-8"
          />
          <Button
            variant="outline"
            size="sm"
            disabled={!newKey || newKey in (value ?? {})}
            onClick={() => {
              onChange({ ...value, [newKey]: 0 });
              setNewKey("");
            }}
          >
            Add
          </Button>
        </div>
      </div>
      {prop.description ? <div className="text-[11px] text-faint mt-1">{prop.description}</div> : null}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Result rendering                                                    */
/* ------------------------------------------------------------------ */

function histogramFromSeries(values: number[], nBins = 40) {
  if (!values.length) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const width = (max - min) / nBins || 1;
  const bins = Array.from({ length: nBins + 1 }, (_, i) => min + i * width);
  const counts = new Array(nBins).fill(0);
  for (const v of values) {
    const i = Math.min(nBins - 1, Math.floor((v - min) / width));
    counts[i] += 1;
  }
  return { bins, counts };
}

function ResultView({ res }: { res: CalcResponse }) {
  const r = res.result;
  const scalarKeys = Object.keys(r).filter((k) => typeof r[k] === "number" || typeof r[k] === "boolean" || typeof r[k] === "string");
  const hist = (r.histogram as { bins: number[]; counts: number[] } | undefined) ?? null;
  const series = (Array.isArray(r.pnl) ? (r.pnl as number[]) : Array.isArray(r.pnl_sorted) ? (r.pnl_sorted as number[]) : null);
  const derived = !hist && series ? histogramFromSeries(series) : null;
  const varValue = typeof r.var === "number" ? r.var : typeof r.var_equal === "number" ? r.var_equal : undefined;
  const esValue = typeof r.es === "number" ? r.es : undefined;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {scalarKeys.map((k) => (
          <KpiTile key={k} label={titleCase(k)} value={typeof r[k] === "number" ? fmtNum(r[k]) : String(r[k])} />
        ))}
      </div>
      {hist ? <ChartHistogram bins={hist.bins} counts={hist.counts} varValue={varValue} esValue={esValue} /> : null}
      {derived ? (
        <ChartHistogram bins={derived.bins} counts={derived.counts} varValue={varValue} esValue={esValue} title="Historical P&L scenarios" />
      ) : null}
      {res.warnings.length ? (
        <div className="border border-amber-200 bg-amber-50 rounded-[var(--rl-radius)] p-3 text-xs text-warn space-y-1">
          {res.warnings.map((w, i) => (
            <div key={i} className="flex gap-2">
              <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
              <span>{w}</span>
            </div>
          ))}
        </div>
      ) : null}
      <CalcTrace trace={res.trace} />
      <div className="text-[11px] text-faint">
        Engine {res.engine_version} · calc <code className="font-mono">{res.calc_id}</code>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Runner                                                              */
/* ------------------------------------------------------------------ */

export function ExerciseRunner({
  calc,
  defaults,
  title,
  description,
  autoRun = true,
}: {
  calc: CalcSummary;
  defaults?: Record<string, unknown>;
  title?: string;
  description?: string;
  autoRun?: boolean;
}) {
  const initial = React.useMemo<Inputs>(() => ({ ...calc.defaults, ...(defaults ?? {}) }), [calc.defaults, defaults]);
  const [inputs, setInputs] = React.useState<Inputs>(initial);
  const [result, setResult] = React.useState<CalcResponse | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  const props = calc.input_schema.properties ?? {};
  const fieldNames = Object.keys(props).length ? Object.keys(props) : Object.keys(initial);

  const run = React.useCallback(
    async (payload: Inputs) => {
      setBusy(true);
      setError(null);
      try {
        setResult(await api.runCalc(calc.id, payload));
      } catch (e) {
        const err = e as { message: string; detail?: unknown };
        const detail = err.detail as { detail?: unknown } | undefined;
        const msg = detail?.detail ? JSON.stringify(detail.detail) : err.message;
        setError(msg);
      } finally {
        setBusy(false);
      }
    },
    [calc.id],
  );

  React.useEffect(() => {
    if (autoRun) void run(initial);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [calc.id]);

  const set = (k: string, v: unknown) => setInputs((s) => ({ ...s, [k]: v }));

  return (
    <div className="border border-border rounded-[var(--rl-radius)] bg-surface-2">
      <div className="px-4 py-3 border-b border-border flex items-start justify-between gap-3 flex-wrap">
        <div>
          <div className="text-sm font-semibold">{title ?? calc.title}</div>
          {description ? <Markdown className="text-xs mt-1 [&_p]:mb-1">{description}</Markdown> : <p className="text-xs text-muted mt-0.5">{calc.description}</p>}
        </div>
        <div className="flex items-center gap-2">
          <ValidationBadge label={calc.validation_label} />
          <SyntheticBadge />
        </div>
      </div>

      <form
        className="p-4 grid grid-cols-1 md:grid-cols-2 gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          void run(inputs);
        }}
      >
        {fieldNames.map((name) => {
          const prop = resolveRef(calc.input_schema, props[name] ?? {});
          const kind = kindOf(prop);
          const value = inputs[name];
          if (kind === "integer" || kind === "number") {
            return <NumberField key={name} name={name} prop={prop} value={Number(value)} onChange={(v) => set(name, v)} />;
          }
          if (kind === "boolean") {
            return (
              <div key={name} className="flex items-center gap-2 pt-5">
                <input
                  id={`f-${name}`}
                  type="checkbox"
                  checked={Boolean(value)}
                  onChange={(e) => set(name, e.target.checked)}
                  className="h-4 w-4 accent-[var(--rl-accent)]"
                />
                <Label htmlFor={`f-${name}`} className="mb-0" title={prop.description}>
                  {prop.title ?? titleCase(name)}
                </Label>
              </div>
            );
          }
          if (kind === "enum") {
            return (
              <div key={name}>
                <Label htmlFor={`f-${name}`} title={prop.description}>{prop.title ?? titleCase(name)}</Label>
                <Select id={`f-${name}`} value={String(value)} onChange={(e) => {
                  const raw = e.target.value;
                  const match = prop.enum!.find((o) => String(o) === raw);
                  set(name, match ?? raw);
                }}>
                  {prop.enum!.map((o) => (
                    <option key={String(o)} value={String(o)}>
                      {String(o)}
                    </option>
                  ))}
                </Select>
              </div>
            );
          }
          if (kind === "object") {
            return (
              <ObjectField
                key={name}
                name={name}
                prop={prop}
                value={(value as Record<string, number>) ?? {}}
                onChange={(v) => set(name, v)}
              />
            );
          }
          return (
            <div key={name}>
              <Label htmlFor={`f-${name}`} title={prop.description}>{prop.title ?? titleCase(name)}</Label>
              <Input id={`f-${name}`} value={String(value ?? "")} onChange={(e) => set(name, e.target.value)} />
            </div>
          );
        })}

        <div className="md:col-span-2 flex items-center gap-2 pt-1">
          <Button type="submit" disabled={busy}>
            <Play className="w-3.5 h-3.5" /> {busy ? "Calculating…" : "Calculate"}
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              setInputs(initial);
              void run(initial);
            }}
          >
            <RotateCcw className="w-3.5 h-3.5" /> Reset
          </Button>
          {calc.regulatory_references.length ? (
            <span className="ml-auto flex items-center gap-1 flex-wrap">
              {calc.regulatory_references.map((r) => (
                <Badge key={r} tone="accent" className="font-mono">
                  {r}
                </Badge>
              ))}
            </span>
          ) : null}
        </div>
      </form>

      <div className="px-4 pb-4">
        {error ? (
          <div role="alert" className="border border-red-200 bg-red-50 rounded-[var(--rl-radius)] p-3 text-xs text-danger break-words">
            {error}
          </div>
        ) : null}
        {result ? <ResultView res={result} /> : !error && busy ? <div className="text-xs text-muted">Running…</div> : null}
      </div>
    </div>
  );
}
