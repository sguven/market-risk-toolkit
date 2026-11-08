/**
 * Typed client for the RiskLab backend (contract: docs/API.md, v1).
 * Server components call these with `cache: 'no-store'`; client components reuse the same helpers.
 */

import { IS_STATIC, resolveStatic } from "./static-api";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type ValidationLabel =
  | "educational"
  | "simplified"
  | "partial-regulatory"
  | "validated-regulatory";

export interface Health {
  status: string;
  engine_version: string;
  regulatory_version: string;
}

export interface TopicSummary {
  slug: string;
  title: string;
  level: string;
  ordinal: number;
  authored: boolean;
}

export interface LearnPath {
  slug: string;
  title: string;
  level: string;
  ordinal: number;
  description: string;
  topics: TopicSummary[];
}

export interface Formula {
  latex: string;
  caption?: string | null;
}

export interface Variable {
  symbol: string;
  name: string;
  meaning: string;
  units?: string | null;
}

export interface WorkedStep {
  label: string;
  math?: string | null;
  result?: string | null;
}

export interface RelatedTopic {
  slug: string;
  title: string;
  authored: boolean;
}

export interface Exercise {
  calc_id: string;
  title: string;
  description: string;
  defaults: Record<string, unknown>;
}

export interface RegRef {
  id: string;
  title: string;
  url: string;
}

export interface Question {
  id: string;
  stem: string;
  choices: string[];
  answer_index: number;
  rationale: string;
}

export interface Topic {
  slug: string;
  path_slug: string;
  title: string;
  level: string;
  summary: string;
  sections: {
    concept: string;
    why_it_matters: string;
    real_world_example: string;
    mathematical_logic: { intro: string; formulas: Formula[] };
    variables: Variable[];
    worked_example: { intro: string; steps: WorkedStep[] };
    related_concepts: RelatedTopic[];
  };
  exercise: Exercise | null;
  regulatory_references: RegRef[];
  questions: Question[];
}

export interface Chapter {
  code: string;
  standard: string;
  title: string;
  effective_date: string;
  last_update: string;
  source_url: string;
  summary: string;
  provision_count: number;
}

export interface ProvisionSummary {
  id: string;
  title: string;
}

export interface ChapterDetail extends Chapter {
  provisions: ProvisionSummary[];
}

export interface Provision {
  id: string;
  chapter_code: string;
  chapter_title: string;
  title: string;
  excerpt: string;
  excerpt_kind: "quote" | "paraphrase";
  plain_language: string;
  technical_interpretation: string;
  mathematical_implications: string;
  related_calculations: { calc_id: string; title: string }[];
  related_topics: RelatedTopic[];
  cross_references: { id: string; title: string; relation: string }[];
  source_url: string;
  effective_date: string;
  last_update: string;
  version_tag: string;
}

export interface SearchHit {
  id: string;
  chapter_code: string;
  title: string;
  snippet: string;
}

export type NodeKind =
  | "regulation"
  | "concept"
  | "model"
  | "calculation"
  | "module";

export interface GraphNode {
  id: string;
  kind: NodeKind;
  label: string;
  href: string;
}

export interface GraphEdge {
  from: string;
  to: string;
  relation: string;
}

export interface Graph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

/** Minimal JSON-schema subset the ExerciseRunner understands. */
export interface JsonSchemaProperty {
  type?: string | string[];
  title?: string;
  description?: string;
  minimum?: number;
  maximum?: number;
  exclusiveMinimum?: number;
  exclusiveMaximum?: number;
  enum?: unknown[];
  default?: unknown;
  anyOf?: JsonSchemaProperty[];
  $ref?: string;
  properties?: Record<string, JsonSchemaProperty>;
  additionalProperties?: JsonSchemaProperty | boolean;
}

export interface JsonSchema extends JsonSchemaProperty {
  properties?: Record<string, JsonSchemaProperty>;
  required?: string[];
  $defs?: Record<string, JsonSchemaProperty>;
}

export interface CalcSummary {
  id: string;
  title: string;
  description: string;
  validation_label: ValidationLabel;
  regulatory_references: string[];
  input_schema: JsonSchema;
  defaults: Record<string, unknown>;
}

export interface TraceStep {
  step: number;
  label: string;
  formula?: string | null;
  inputs: Record<string, unknown>;
  output: unknown;
  reference?: string | null;
}

export interface CalcResponse {
  calc_id: string;
  engine_version: string;
  validation_label: ValidationLabel;
  result: Record<string, unknown>;
  trace: TraceStep[];
  warnings: string[];
}

export interface Dashboard {
  simulators: CalcSummary[];
  regulatory_updates: {
    code: string;
    title: string;
    last_update: string;
    source_url: string;
  }[];
  featured: { calc_id: string; title: string; blurb: string }[];
  stats?: { topics_authored: number; topics_total: number; chapters: number; provisions: number; simulators: number };
  paths: {
    slug: string;
    title: string;
    authored_count: number;
    total_count: number;
  }[];
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public detail?: unknown,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (IS_STATIC) {
    try {
      return await resolveStatic<T>(path, init);
    } catch (e) {
      throw new ApiError((e as Error).message, (e as { status?: number }).status ?? 500);
    }
  }
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { cache: "no-store", ...init });
  } catch (e) {
    throw new ApiError(
      `Cannot reach the RiskLab API at ${API_BASE}. Is the backend running? (${(e as Error).message})`,
      0,
    );
  }
  if (!res.ok) {
    let detail: unknown;
    try {
      detail = await res.json();
    } catch {
      detail = await res.text().catch(() => undefined);
    }
    throw new ApiError(`${res.status} ${res.statusText} for ${path}`, res.status, detail);
  }
  return (await res.json()) as T;
}

export const api = {
  health: () => request<Health>("/api/health"),
  learnPaths: () => request<LearnPath[]>("/api/learn/paths"),
  topic: (slug: string) =>
    request<Topic>(`/api/learn/topics/${encodeURIComponent(slug)}`),
  chapters: () => request<Chapter[]>("/api/regulatory/chapters"),
  chapter: (code: string) =>
    request<ChapterDetail>(`/api/regulatory/chapters/${encodeURIComponent(code)}`),
  provision: (id: string) =>
    request<Provision>(`/api/regulatory/provisions/${encodeURIComponent(id)}`),
  search: (q: string) =>
    request<SearchHit[]>(`/api/regulatory/search?q=${encodeURIComponent(q)}`),
  graph: () => request<Graph>("/api/regulatory/graph"),
  calcs: () => request<CalcSummary[]>("/api/calc"),
  runCalc: (id: string, inputs: Record<string, unknown>) =>
    request<CalcResponse>(`/api/calc/${encodeURIComponent(id)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(inputs),
    }),
  dashboard: () => request<Dashboard>("/api/dashboard"),
};

/** Resolve a result wrapper so pages never throw: `{ data } | { error }`. */
export type SafeResult<T> =
  | { ok: true; data: T; error: null }
  | { ok: false; data: null; error: string };

export async function safe<T>(p: Promise<T>): Promise<SafeResult<T>> {
  try {
    return { ok: true, data: await p, error: null };
  } catch (e) {
    return { ok: false, data: null, error: (e as Error).message };
  }
}

/** "MAR21.4" -> "MAR21" */
export function chapterOf(provisionId: string): string {
  return provisionId.split(".")[0];
}
