/**
 * Parity test: TypeScript engine vs the Python reference (fixtures exported by
 * backend/scripts/export_static.py). Run with `npm run parity`.
 *
 *  - deterministic calcs (parametric, liquidity horizon, FX option): every numeric field to 1e-9 relative
 *  - simulated calcs: VaR/ES within a statistical tolerance (different PRNG streams, same distribution)
 */
import fixtures from "../lib/data/fixtures.json";
import snapshot from "../lib/data/snapshot.json";
import { runCalcLocal } from "../lib/engine/calcs";
import type { CalcSummary } from "../lib/api";

const calcs = new Map((snapshot.calcs as unknown as CalcSummary[]).map((c) => [c.id, c]));
const DETERMINISTIC = new Set(["var_es_parametric", "liquidity_horizon_scaling", "fx_option_gk"]);
let failures = 0, checks = 0;

function close(a: number, b: number, rel: number, label: string) {
  checks++;
  const ok = Math.abs(a - b) <= rel * Math.max(1e-12, Math.abs(b));
  if (!ok) { failures++; console.error(`  ✗ ${label}: ts=${a} py=${b} (rel ${Math.abs(a - b) / Math.abs(b)})`); }
}

for (const f of fixtures as { calc_id: string; inputs: Record<string, unknown>; expected: { result: Record<string, unknown> } }[]) {
  const summary = calcs.get(f.calc_id)!;
  const out = runCalcLocal(summary, f.inputs);
  const py = f.expected.result, ts = out.result;
  console.log(`${f.calc_id} ${JSON.stringify(f.inputs)}`);
  if (DETERMINISTIC.has(f.calc_id)) {
    for (const [k, v] of Object.entries(py)) {
      if (typeof v === "number") close(ts[k] as number, v, 1e-9, k);
      else if (Array.isArray(v) && typeof v[0] === "object") {
        (v as Record<string, number>[]).forEach((row, i) => Object.entries(row).forEach(([kk, vv]) => close((ts[k] as Record<string, number>[])[i][kk], vv, 1e-9, `${k}[${i}].${kk}`)));
      }
    }
  } else if (f.calc_id === "var_es_historical") {
    close(ts.var as number, py.var as number, 0.08, "var (statistical)");
    close(ts.es as number, py.es as number, 0.08, "es (statistical)");
    close(ts.normal_es_over_var as number, py.normal_es_over_var as number, 1e-9, "normal_es_over_var");
    close((ts.histogram as { counts: number[] }).counts.length, 40, 0, "histogram bins");
  } else if (f.calc_id === "historical_var_fx") {
    // Different random paths → only structural checks and the ES ≥ VaR identity.
    checks += 3;
    const ok = (ts.pnl as number[]).length === (py._n_pnl as number) && (ts.var_equal as number) > 0 && (ts.es_equal as number) >= (ts.var_equal as number);
    if (!ok) { failures++; console.error("  ✗ structural check failed"); }
  }
}
console.log(`\n${checks} checks, ${failures} failures`);
if (failures) process.exit(1);
