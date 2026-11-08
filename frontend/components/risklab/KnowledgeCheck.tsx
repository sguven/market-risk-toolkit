"use client";
import * as React from "react";
import { CheckCircle2, XCircle } from "lucide-react";
import type { Question } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Markdown } from "./Markdown";
import { markCompleted, getProgress } from "@/lib/progress";
import { cn } from "@/lib/utils";

/** Exam-style MCQ block. Stores the score in localStorage when all questions are answered. */
export function KnowledgeCheck({ slug, questions }: { slug: string; questions: Question[] }) {
  const [answers, setAnswers] = React.useState<Record<string, number>>({});
  const [revealed, setRevealed] = React.useState<Record<string, boolean>>({});
  const [saved, setSaved] = React.useState<number | null>(null);

  React.useEffect(() => {
    const p = getProgress()[slug];
    if (p?.status === "completed" && typeof p.score === "number") setSaved(p.score);
  }, [slug]);

  const allRevealed = questions.length > 0 && questions.every((q) => revealed[q.id]);
  const correct = questions.filter((q) => answers[q.id] === q.answer_index).length;

  React.useEffect(() => {
    if (allRevealed) {
      const score = correct / questions.length;
      markCompleted(slug, score);
      setSaved(score);
    }
  }, [allRevealed, correct, questions.length, slug]);

  if (!questions.length) {
    return <p className="text-sm text-muted">No knowledge-check questions for this topic yet.</p>;
  }

  return (
    <div className="space-y-4">
      {saved !== null ? (
        <Badge tone="ok">Last score: {Math.round(saved * 100)}%</Badge>
      ) : null}
      {questions.map((q, qi) => {
        const chosen = answers[q.id];
        const isRevealed = revealed[q.id];
        return (
          <div key={q.id} className="border border-border rounded-[var(--rl-radius)] bg-surface p-4">
            <div className="text-sm font-medium mb-3">
              <span className="text-muted mr-2 tnum">Q{qi + 1}.</span>
              {q.stem}
            </div>
            <div className="space-y-1.5">
              {q.choices.map((c, ci) => {
                const isAnswer = ci === q.answer_index;
                const isChosen = chosen === ci;
                return (
                  <button
                    key={ci}
                    type="button"
                    disabled={isRevealed}
                    onClick={() => setAnswers((a) => ({ ...a, [q.id]: ci }))}
                    className={cn(
                      "w-full text-left text-sm border rounded-[var(--rl-radius)] px-3 py-2 flex items-start gap-2 transition-colors",
                      !isRevealed && isChosen && "border-accent bg-accent-soft",
                      !isRevealed && !isChosen && "border-border hover:bg-surface-2",
                      isRevealed && isAnswer && "border-green-300 bg-green-50",
                      isRevealed && isChosen && !isAnswer && "border-red-300 bg-red-50",
                      isRevealed && !isChosen && !isAnswer && "border-border opacity-70",
                    )}
                  >
                    <span className="font-mono text-xs text-muted mt-0.5 w-4">{String.fromCharCode(65 + ci)}</span>
                    <span className="flex-1">{c}</span>
                    {isRevealed && isAnswer ? <CheckCircle2 className="w-4 h-4 text-ok shrink-0" /> : null}
                    {isRevealed && isChosen && !isAnswer ? <XCircle className="w-4 h-4 text-danger shrink-0" /> : null}
                  </button>
                );
              })}
            </div>
            <div className="mt-3 flex items-start gap-3">
              {!isRevealed ? (
                <Button
                  size="sm"
                  variant="outline"
                  disabled={chosen === undefined}
                  onClick={() => setRevealed((r) => ({ ...r, [q.id]: true }))}
                >
                  Check answer
                </Button>
              ) : (
                <div className="text-xs text-muted">
                  <span className={cn("font-medium", chosen === q.answer_index ? "text-ok" : "text-danger")}>
                    {chosen === q.answer_index ? "Correct." : "Not quite."}
                  </span>{" "}
                  <Markdown className="inline [&_p]:inline [&_p]:mb-0 text-xs">{q.rationale}</Markdown>
                </div>
              )}
            </div>
          </div>
        );
      })}
      {allRevealed ? (
        <div className="text-sm">
          Score: <span className="font-semibold tnum">{correct}/{questions.length}</span> — progress saved on this device.
        </div>
      ) : null}
    </div>
  );
}
