/**
 * TypeScript port of backend/risklab_engine/calcs/registry.py for static (GitHub Pages) mode.
 *
 * The Python engine is the reference. Each function here mirrors its Python twin step for step,
 * including the calculation trace and warnings. Deterministic calcs are verified bit-for-bit
 * (to 1e-9 relative) and simulated calcs statistically by scripts/parity.ts.
 */
import type { CalcResponse, CalcSummary, TraceStep, ValidationLabel } from "../api";
import {
  histogram, makeNormal, makeRng, mean, normCdf, normPdf, normPpf, quantileLinear, stdSample, studentT,
} from "./math";

export const ENGINE_VERSION = "0.1.0-ts";

class Trace {
  steps: TraceStep[] = [];
  warnings: string[] = [];
  add(label: string, output: unknown, opts: { formula?: string; inputs?: Record<string, unknown>; reference?: string | null } = {}) {
    this.steps.push({ step: this.steps.length + 1, label, formula: opts.formula ?? null, inputs: opts.inputs ?? {}, output: fmt(output), reference: opts.reference ?? null });
  }
  warn(m: string) { this.warnings.push(m); }
}

function fmt(v: unknown): string {
  if (typeof v === "number") return Math.abs(v) >= 1000 ? v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : Number(v.toPrecision(6)).toString();
  return String(v);
}

// ---------------------------------------------------------------- shared formulas
const POSITION_VALUE = 1_000_000;
const LIQUIDITY_HORIZONS = [10, 20, 40, 60, 120] as const;

function checkConf(c: number) { if (!(c > 0 && c < 1)) throw new Error("confidence must be strictly between 0 and 1"); }

export function historicalVar(pnl: number[], confidence: number): number {
  checkConf(confidence);
  const s = [...pnl].sort((a, b) => a - b);
  return -quantileLinear(s, 1 - confidence);
}

export function historicalEs(pnl: number[], confidence: number): number {
  checkConf(confidence);
  const x = [...pnl].sort((a, b) => a - b);
  const n = x.length, alpha = 1 - confidence, mass = alpha * n;
  const k = Math.floor(mass), frac = mass - k;
  let tail = 0;
  for (let i = 0; i < k; i++) tail += x[i];
  if (k < n && frac > 1e-12) tail += frac * x[k];
  return -(tail / mass);
}

export function ageWeightedVar(pnl: number[], confidence: number, decay: number): number {
  checkConf(confidence);
  const n = pnl.length;
  const idx = pnl.map((_, i) => i).sort((a, b) => pnl[a] - pnl[b]);
  const w = (i: number) => Math.pow(decay, n - 1 - i) * (1 - decay) / (1 - Math.pow(decay, n));
  const alpha = 1 - confidence;
  let cum = 0, prevCum = 0;
  for (let j = 0; j < idx.length; j++) {
    prevCum = cum; cum += w(idx[j]);
    if (cum >= alpha) {
      if (j === 0) return -pnl[idx[0]];
      const t = (alpha - prevCum) / (cum - prevCum);
      const a = pnl[idx[j - 1]], b = pnl[idx[j]];
      return -(a + t * (b - a));
    }
  }
  return -pnl[idx[idx.length - 1]];
}

export const normalZ = (c: number) => normPpf(c);
export const normalEsFactor = (c: number) => normPdf(normPpf(c)) / (1 - c);

export function liquidityAdjustedEs(esBase: number, byBucket: Record<number, number>, t?: Trace): number {
  if (esBase < 0) throw new Error("es_base must be non-negative");
  let total = esBase ** 2;
  t?.add("Base term ES_T(P)^2", esBase ** 2, { formula: "ES_T(P)^2", inputs: { "ES_T(P)": esBase }, reference: "MAR33.4" });
  for (let j = 1; j < LIQUIDITY_HORIZONS.length; j++) {
    const lh = LIQUIDITY_HORIZONS[j], prev = LIQUIDITY_HORIZONS[j - 1];
    const esj = byBucket[lh] ?? 0;
    if (esj < 0) throw new Error("ES components must be non-negative");
    if (esj > esBase * (1 + 1e-9)) t?.warn(`ES_T(P,${lh}) exceeds ES_T(P); possible if the excluded factors were hedging.`);
    const term = (esj * Math.sqrt((lh - prev) / 10)) ** 2;
    total += term;
    t?.add(`Bucket j=${j + 1} (LH=${lh}d) term`, term, {
      formula: "\\left(ES_T(P,j)\\sqrt{\\tfrac{LH_j - LH_{j-1}}{T}}\\right)^2",
      inputs: { "ES_T(P,j)": esj, LH_j: lh, "LH_j-1": prev, T: 10 }, reference: "MAR33.4",
    });
  }
  const es = Math.sqrt(total);
  t?.add("Liquidity-adjusted ES", es, { formula: "ES=\\sqrt{\\text{sum of terms}}", reference: "MAR33.4" });
  return es;
}

export function garmanKohlhagen(S: number, K: number, days: number, rd: number, rf: number, vol: number, option: "call" | "put", notional: number) {
  const t = days / 365;
  const d1 = (Math.log(S / K) + (rd - rf + vol * vol / 2) * t) / (vol * Math.sqrt(t));
  const d2 = d1 - vol * Math.sqrt(t);
  const dfd = Math.exp(-rd * t), dff = Math.exp(-rf * t);
  const price = option === "call" ? S * dff * normCdf(d1) - K * dfd * normCdf(d2) : K * dfd * normCdf(-d2) - S * dff * normCdf(-d1);
  return { pv: notional * price, d1, d2, t };
}

// ---------------------------------------------------------------- calcs
type Inputs = Record<string, unknown>;
type Runner = (p: Inputs) => { result: Record<string, unknown>; trace: Trace };

const num = (p: Inputs, k: string) => Number(p[k]);
const str = (p: Inputs, k: string) => String(p[k]);

const runners: Record<string, Runner> = {
  var_es_historical(p) {
    const t = new Trace();
    const n = num(p, "n_scenarios"), vol = num(p, "daily_vol"), conf = num(p, "confidence"), seed = num(p, "seed");
    const dist = str(p, "distribution"), df = num(p, "df");
    const rng = makeRng(seed), normal = makeNormal(rng);
    const pnl: number[] = new Array(n);
    for (let i = 0; i < n; i++) {
      const eps = dist === "normal" ? normal() : studentT(df, rng, normal) / Math.sqrt(df / (df - 2));
      pnl[i] = POSITION_VALUE * vol * eps;
    }
    t.add("Generate synthetic daily P&L scenarios", `${n} scenarios`, { formula: "P\\&L_i = V\\,\\sigma\\,\\varepsilon_i", inputs: { V: POSITION_VALUE, sigma: vol, distribution: dist, seed } });
    const v = historicalVar(pnl, conf);
    t.add("Historical VaR = −(1 − α) empirical quantile", v, { formula: "\\mathrm{VaR}_\\alpha = -Q_{1-\\alpha}(P\\&L)", inputs: { alpha: conf } });
    const es = historicalEs(pnl, conf);
    t.add("Historical ES = mean loss beyond VaR", es, { formula: "\\mathrm{ES}_\\alpha = -\\,\\mathbb{E}[P\\&L \\mid P\\&L \\le -\\mathrm{VaR}_\\alpha]", inputs: { alpha: conf }, reference: Math.abs(conf - 0.975) < 1e-9 ? "MAR33.3" : null });
    t.add("ES / VaR ratio", v ? es / v : NaN, { formula: "\\mathrm{ES}_\\alpha / \\mathrm{VaR}_\\alpha" });
    if (Math.abs(conf - 0.975) > 1e-9) t.warn("FRTB IMA uses ES at 97.5% (MAR33.3); other confidence levels are shown for education only.");
    t.warn("Synthetic data: scenarios are random draws, not market history.");
    const sorted = [...pnl].sort((a, b) => a - b);
    let varIndex = 0; while (varIndex < n && sorted[varIndex] < -v) varIndex++;
    return {
      result: {
        position_value: POSITION_VALUE, var: v, es, es_over_var: v ? es / v : null,
        normal_es_over_var: normalEsFactor(conf) / normalZ(conf), mean: mean(pnl), std: stdSample(pnl),
        var_index: varIndex, pnl_sorted: sorted.map((x) => Math.round(x * 100) / 100), histogram: histogram(pnl, 40),
      }, trace: t,
    };
  },

  var_es_parametric(p) {
    const t = new Trace();
    const V = num(p, "position_value"), vol = num(p, "daily_vol"), conf = num(p, "confidence"), h = num(p, "horizon_days");
    const z = normalZ(conf);
    t.add("Standard-normal quantile z_α", z, { formula: "z_\\alpha = \\Phi^{-1}(\\alpha)", inputs: { alpha: conf } });
    const f = normalEsFactor(conf);
    t.add("Normal ES factor φ(z_α)/(1−α)", f, { formula: "\\frac{\\varphi(z_\\alpha)}{1-\\alpha}" });
    const v = Math.abs(V) * vol * z * Math.sqrt(h);
    t.add("Parametric VaR", v, { formula: "\\mathrm{VaR} = V\\,\\sigma\\,z_\\alpha\\sqrt{h}", inputs: { V, sigma: vol, h } });
    const es = Math.abs(V) * vol * f * Math.sqrt(h);
    t.add("Parametric ES", es, { formula: "\\mathrm{ES} = V\\,\\sigma\\,\\frac{\\varphi(z_\\alpha)}{1-\\alpha}\\sqrt{h}" });
    t.warn("Normal distribution assumed; real P&L has fat tails, which is one reason FRTB moved to ES.");
    return { result: { var: v, es, z, es_factor: f, es_over_var: es / v }, trace: t };
  },

  liquidity_horizon_scaling(p) {
    const t = new Trace();
    const base = num(p, "es_base");
    const buckets = { 20: num(p, "es_lh20"), 40: num(p, "es_lh40"), 60: num(p, "es_lh60"), 120: num(p, "es_lh120") };
    const es = liquidityAdjustedEs(base, buckets, t);
    const lh = num(p, "single_horizon");
    if (!LIQUIDITY_HORIZONS.includes(lh as 10)) throw new Error("single_horizon must be one of 10,20,40,60,120");
    const single = base * Math.sqrt(lh / 10);
    t.add(`Intuition: all factors at LH=${lh}d`, single, { formula: "ES_T(P)\\sqrt{LH/T}", inputs: { LH: lh, T: 10 }, reference: "MAR33.4" });
    t.warn("Inputs ES_T(P,j) are supplied, not computed from a portfolio; the full IMA engine arrives in Phase 4.");
    const vals = [buckets[20], buckets[40], buckets[60], buckets[120]];
    return {
      result: {
        es_liquidity_adjusted: es, uplift_vs_base: base ? es / base : null, single_horizon_es: single,
        single_horizon_factor: base ? single / base : null, horizons: [...LIQUIDITY_HORIZONS],
        terms: LIQUIDITY_HORIZONS.slice(1).map((l, i) => ({ lh: l, es: vals[i], scale: Math.sqrt((l - LIQUIDITY_HORIZONS[i]) / 10) })),
      }, trace: t,
    };
  },

  fx_option_gk(p) {
    const t = new Trace();
    const S = num(p, "spot"), K = num(p, "strike"), rd = num(p, "r_dom"), rf = num(p, "r_for"), vol = num(p, "vol");
    const days = num(p, "days"), N = num(p, "notional"), option = str(p, "option") as "call" | "put";
    const { pv, d1, d2, t: tt } = garmanKohlhagen(S, K, days, rd, rf, vol, option, N);
    t.add("d1", d1, { formula: "d_1=\\frac{\\ln(S/K)+(r_d-r_f+\\sigma^2/2)t}{\\sigma\\sqrt t}", inputs: { S, K, r_d: rd, r_f: rf, sigma: vol, t: tt } });
    t.add("d2", d2, { formula: "d_2=d_1-\\sigma\\sqrt t" });
    t.add(`${option[0].toUpperCase()}${option.slice(1)} PV (domestic ccy)`, pv, { formula: option === "call" ? "C=S e^{-r_f t}N(d_1)-K e^{-r_d t}N(d_2)" : "P=K e^{-r_d t}N(-d_2)-S e^{-r_f t}N(-d_1)" });
    const bump = S * 1e-4;
    const up = garmanKohlhagen(S + bump, K, days, rd, rf, vol, option, N).pv;
    const dn = garmanKohlhagen(S - bump, K, days, rd, rf, vol, option, N).pv;
    const delta = (up - dn) / (2 * bump);
    t.add("Spot delta (central finite difference)", delta, { formula: "\\Delta\\approx\\frac{PV(S+h)-PV(S-h)}{2h}", inputs: { h: bump } });
    return { result: { pv, d1, d2, delta, forward: S * Math.exp((rd - rf) * tt) }, trace: t };
  },

  historical_var_fx(p) {
    const t = new Trace();
    const nDays = num(p, "n_days"), seed = num(p, "seed"), conf = num(p, "confidence"), decay = num(p, "decay");
    const rng = makeRng(seed), normal = makeNormal(rng);
    const spec: [string, number, number][] = [["USD", 30, 0.006], ["EUR", 33, 0.007], ["GBP", 39, 0.008]];
    const positions: Record<string, number> = { USD: num(p, "usd"), EUR: num(p, "eur"), GBP: num(p, "gbp") };
    const series: Record<string, number[]> = {};
    for (const [c, s0, v] of spec) {
      let cum = 0; series[c] = new Array(nDays);
      for (let i = 0; i < nDays; i++) { cum += normal() * v; series[c][i] = s0 * Math.exp(cum); }
    }
    t.add("Simulate FX rate history (synthetic)", `${nDays} days × 3 currencies`, { inputs: { seed } });
    const pnl: number[] = new Array(nDays - 1).fill(0);
    const spotToday: Record<string, number> = {};
    for (const [c] of spec) {
      const s = series[c]; spotToday[c] = Math.round(s[nDays - 1] * 1e4) / 1e4;
      const exposure = s[nDays - 1] * positions[c];
      for (let i = 1; i < nDays; i++) pnl[i - 1] += (s[i] / s[i - 1] - 1) * exposure;
    }
    t.add("Daily P&L scenarios from historical returns", `${pnl.length} scenarios`, { formula: "P\\&L_t=\\sum_c S_{c,\\text{today}}\\,q_c\\,(S_{c,t}/S_{c,t-1}-1)" });
    const vEq = historicalVar(pnl, conf);
    t.add("Equal-weight historical VaR", vEq, { formula: "-Q_{1-\\alpha}(P\\&L)" });
    const vAw = ageWeightedVar(pnl, conf, decay);
    t.add("Age-weighted (BRW) VaR", vAw, { formula: "w_k=\\lambda^k\\frac{1-\\lambda}{1-\\lambda^n}", inputs: { lambda: decay } });
    const es = historicalEs(pnl, conf);
    t.add("Equal-weight historical ES", es);
    t.warn("Synthetic FX history (random walk); exposures are illustrative.");
    return { result: { var_equal: vEq, var_age_weighted: vAw, es_equal: es, pnl: pnl.map((x) => Math.round(x * 100) / 100), spot_today: spotToday }, trace: t };
  },
};

/** Validate inputs against the (Python-generated) JSON schema: bounds, enums, defaults. */
export function validateInputs(summary: CalcSummary, raw: Inputs): Inputs {
  const out: Inputs = {};
  const props = summary.input_schema.properties ?? {};
  for (const [k, prop] of Object.entries(props)) {
    let v = raw[k] ?? summary.defaults[k];
    const enumVals = prop.enum ?? prop.anyOf?.flatMap((a) => a.enum ?? []);
    const isNumeric = prop.type === "number" || prop.type === "integer" || (Array.isArray(prop.type) && prop.type.includes("number"));
    if (enumVals && enumVals.length) {
      const match = enumVals.find((e) => String(e) === String(v));
      if (match === undefined) throw new Error(`${k}: must be one of ${enumVals.join(", ")}`);
      v = match;
    } else if (isNumeric || typeof summary.defaults[k] === "number") {
      const n = Number(v);
      if (!Number.isFinite(n)) throw new Error(`${k}: must be a number`);
      if (prop.type === "integer" && !Number.isInteger(n)) throw new Error(`${k}: must be an integer`);
      if (prop.minimum !== undefined && n < prop.minimum) throw new Error(`${k}: must be ≥ ${prop.minimum}`);
      if (prop.maximum !== undefined && n > prop.maximum) throw new Error(`${k}: must be ≤ ${prop.maximum}`);
      if (prop.exclusiveMinimum !== undefined && n <= prop.exclusiveMinimum) throw new Error(`${k}: must be > ${prop.exclusiveMinimum}`);
      if (prop.exclusiveMaximum !== undefined && n >= prop.exclusiveMaximum) throw new Error(`${k}: must be < ${prop.exclusiveMaximum}`);
      v = n;
    }
    out[k] = v;
  }
  return out;
}

export function runCalcLocal(summary: CalcSummary, raw: Inputs): CalcResponse {
  const runner = runners[summary.id];
  if (!runner) throw new Error(`Unknown calculation ${summary.id}`);
  const inputs = validateInputs(summary, raw);
  const { result, trace } = runner(inputs);
  return {
    calc_id: summary.id, engine_version: ENGINE_VERSION, validation_label: summary.validation_label as ValidationLabel,
    result, trace: trace.steps, warnings: trace.warnings,
  };
}
