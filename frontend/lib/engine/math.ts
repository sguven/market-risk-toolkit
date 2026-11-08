/**
 * Numerical primitives for the client-side engine (static / GitHub Pages mode).
 * The Python engine (backend/risklab_engine) is the reference implementation; this port is
 * checked against it by scripts/parity.ts.
 */

/** Standard-normal pdf. */
export function normPdf(x: number): number {
  return Math.exp(-0.5 * x * x) / Math.sqrt(2 * Math.PI);
}

/** erf via a high-precision rational approximation (W. J. Cody), |error| < 1e-15 on the real line. */
export function erf(x: number): number {
  const ax = Math.abs(x);
  let r: number;
  if (ax < 0.5) {
    const t = x * x;
    const p = [3.16112374387056560e0, 1.13864154151050156e2, 3.77485237685302021e2, 3.20937758913846947e3, 1.85777706184603153e-1];
    const q = [2.36012909523441209e1, 2.44024637934444173e2, 1.28261652607737228e3, 2.84423683343917062e3];
    let num = p[4] * t, den = t;
    for (let i = 0; i < 3; i++) { num = (num + p[i]) * t; den = (den + q[i]) * t; }
    return x * (num + p[3]) / (den + q[3]);
  } else if (ax <= 4) {
    const p = [5.64188496988670089e-1, 8.88314979438837594e0, 6.61191906371416295e1, 2.98635138197400131e2, 8.81952221241769090e2, 1.71204761263407058e3, 2.05107837782607147e3, 1.23033935479799725e3, 2.15311535474403846e-8];
    const q = [1.57449261107098347e1, 1.17693950891312499e2, 5.37181101862009858e2, 1.62138957456669019e3, 3.29079923573345963e3, 4.36261909014324716e3, 3.43936767414372164e3, 1.23033935480374942e3];
    let num = p[8] * ax, den = ax;
    for (let i = 0; i < 7; i++) { num = (num + p[i]) * ax; den = (den + q[i]) * ax; }
    const erfc = Math.exp(-ax * ax) * (num + p[7]) / (den + q[7]);
    r = 1 - erfc;
  } else {
    const p = [3.05326634961232344e-1, 3.60344899949804439e-1, 1.25781726111229246e-1, 1.60837851487422766e-2, 6.58749161529837803e-4, 1.63153871373020978e-2];
    const q = [2.56852019228982242e0, 1.87295284992346725e0, 5.27905102951428412e-1, 6.05183413124413191e-2, 2.33520497626869185e-3];
    const z = 1 / (ax * ax);
    let num = p[5] * z, den = z;
    for (let i = 0; i < 4; i++) { num = (num + p[i]) * z; den = (den + q[i]) * z; }
    let erfc = z * (num + p[4]) / (den + q[4]);
    erfc = (1 / Math.sqrt(Math.PI) - erfc) / ax;
    erfc *= Math.exp(-ax * ax);
    r = 1 - erfc;
  }
  return x < 0 ? -r : r;
}

export function normCdf(x: number): number {
  return 0.5 * (1 + erf(x / Math.SQRT2));
}

/** Inverse normal CDF: Acklam's algorithm with one Halley refinement step (≈ 1e-15 relative). */
export function normPpf(p: number): number {
  if (p <= 0 || p >= 1) throw new Error("p must be in (0,1)");
  const a = [-3.969683028665376e1, 2.209460984245205e2, -2.759285104469687e2, 1.383577518672690e2, -3.066479806614716e1, 2.506628277459239e0];
  const b = [-5.447609879822406e1, 1.615858368580409e2, -1.556989798598866e2, 6.680131188771972e1, -1.328068155288572e1];
  const c = [-7.784894002430293e-3, -3.223964580411365e-1, -2.400758277161838e0, -2.549732539343734e0, 4.374664141464968e0, 2.938163982698783e0];
  const d = [7.784695709041462e-3, 3.224671290700398e-1, 2.445134137142996e0, 3.754408661907416e0];
  const plow = 0.02425, phigh = 1 - plow;
  let x: number;
  if (p < plow) {
    const q = Math.sqrt(-2 * Math.log(p));
    x = (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1);
  } else if (p <= phigh) {
    const q = p - 0.5, r = q * q;
    x = (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1);
  } else {
    const q = Math.sqrt(-2 * Math.log(1 - p));
    x = -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1);
  }
  // Halley refinement
  const e = normCdf(x) - p;
  const u = e * Math.sqrt(2 * Math.PI) * Math.exp(x * x / 2);
  x = x - u / (1 + x * u / 2);
  return x;
}

/** Deterministic PRNG (sfc32) seeded from an integer. Not the same stream as NumPy's PCG64 —
 *  simulated calcs are compared to Python statistically, not bit-for-bit. */
export function makeRng(seed: number): () => number {
  let a = 0x9e3779b9 ^ seed, b = 0x243f6a88 ^ (seed * 2654435761 >>> 0), c = 0xb7e15162, d = seed >>> 0 || 1;
  const next = () => {
    a >>>= 0; b >>>= 0; c >>>= 0; d >>>= 0;
    let t = (a + b) | 0;
    a = b ^ (b >>> 9);
    b = (c + (c << 3)) | 0;
    c = (c << 21) | (c >>> 11);
    d = (d + 1) | 0;
    t = (t + d) | 0;
    c = (c + t) | 0;
    return (t >>> 0) / 4294967296;
  };
  for (let i = 0; i < 20; i++) next(); // warm up
  return next;
}

/** Standard normal draws via Box–Muller. */
export function makeNormal(rng: () => number): () => number {
  let spare: number | null = null;
  return () => {
    if (spare !== null) { const s = spare; spare = null; return s; }
    let u = 0, v = 0;
    while (u === 0) u = rng();
    v = rng();
    const r = Math.sqrt(-2 * Math.log(u)), th = 2 * Math.PI * v;
    spare = r * Math.sin(th);
    return r * Math.cos(th);
  };
}

/** Gamma(shape, 1) via Marsaglia–Tsang (shape ≥ 1 handled directly; < 1 by boosting). */
export function gammaSample(shape: number, rng: () => number, normal: () => number): number {
  if (shape < 1) return gammaSample(shape + 1, rng, normal) * Math.pow(rng(), 1 / shape);
  const d = shape - 1 / 3, c = 1 / Math.sqrt(9 * d);
  for (;;) {
    let x: number, v: number;
    do { x = normal(); v = 1 + c * x; } while (v <= 0);
    v = v * v * v;
    const u = rng();
    if (u < 1 - 0.0331 * x ** 4) return d * v;
    if (Math.log(u) < 0.5 * x * x + d * (1 - v + Math.log(v))) return d * v;
  }
}

/** Student-t draw with df degrees of freedom. */
export function studentT(df: number, rng: () => number, normal: () => number): number {
  const chi2 = 2 * gammaSample(df / 2, rng, normal);
  return normal() / Math.sqrt(chi2 / df);
}

export function quantileLinear(sorted: number[], q: number): number {
  // NumPy default (linear interpolation, method 7)
  const n = sorted.length;
  const h = (n - 1) * q;
  const lo = Math.floor(h), hi = Math.min(lo + 1, n - 1);
  return sorted[lo] + (h - lo) * (sorted[hi] - sorted[lo]);
}

export function mean(xs: number[]): number {
  return xs.reduce((s, x) => s + x, 0) / xs.length;
}

export function stdSample(xs: number[]): number {
  const m = mean(xs);
  return Math.sqrt(xs.reduce((s, x) => s + (x - m) ** 2, 0) / (xs.length - 1));
}

export function histogram(xs: number[], bins = 40): { bins: number[]; counts: number[] } {
  let lo = Infinity, hi = -Infinity;
  for (const x of xs) { if (x < lo) lo = x; if (x > hi) hi = x; }
  if (lo === hi) { lo -= 0.5; hi += 0.5; }
  const width = (hi - lo) / bins;
  const edges = Array.from({ length: bins + 1 }, (_, i) => lo + i * width);
  const counts = new Array(bins).fill(0);
  for (const x of xs) {
    let k = Math.floor((x - lo) / width);
    if (k === bins) k = bins - 1;
    counts[k]++;
  }
  return { bins: edges.map((e) => Math.round(e * 100) / 100), counts };
}
