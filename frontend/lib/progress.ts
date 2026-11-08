"use client";

/**
 * Client-side learning progress (Phase 1: no auth, localStorage only).
 * Keys follow docs/API.md: `risklab.progress.v1`, `risklab.recent.v1`.
 */

export const PROGRESS_KEY = "risklab.progress.v1";
export const RECENT_KEY = "risklab.recent.v1";

export interface ProgressEntry {
  status: "viewed" | "completed";
  score?: number; // 0..1
  updatedAt: string;
}

export type ProgressMap = Record<string, ProgressEntry>;

export interface RecentEntry {
  slug: string;
  title: string;
  viewedAt: string;
}

function read<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function write(key: string, value: unknown) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage may be unavailable (private mode); progress is a convenience only */
  }
}

export function getProgress(): ProgressMap {
  return read<ProgressMap>(PROGRESS_KEY, {});
}

export function markViewed(slug: string) {
  const p = getProgress();
  if (!p[slug]) {
    p[slug] = { status: "viewed", updatedAt: new Date().toISOString() };
    write(PROGRESS_KEY, p);
  }
}

export function markCompleted(slug: string, score: number) {
  const p = getProgress();
  p[slug] = { status: "completed", score, updatedAt: new Date().toISOString() };
  write(PROGRESS_KEY, p);
}

export function getRecent(): RecentEntry[] {
  return read<RecentEntry[]>(RECENT_KEY, []);
}

export function pushRecent(slug: string, title: string) {
  const list = getRecent().filter((r) => r.slug !== slug);
  list.unshift({ slug, title, viewedAt: new Date().toISOString() });
  write(RECENT_KEY, list.slice(0, 8));
}
