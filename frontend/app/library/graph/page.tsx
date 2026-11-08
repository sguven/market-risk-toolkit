import { api, safe } from "@/lib/api";
import { PageHeader } from "@/components/risklab/PageHeader";
import { ErrorPanel } from "@/components/risklab/ErrorPanel";
import { KnowledgeGraph } from "@/components/risklab/KnowledgeGraph";

export default async function GraphPage() {
  const res = await safe(api.graph());
  return (
    <>
      <PageHeader
        title="Regulatory knowledge graph"
        description="How regulations, concepts, models, calculations and learning modules connect — e.g. FRTB IMA → Expected Shortfall → Liquidity horizons → MAR31 → IMA capital → MAR33."
        crumbs={[{ label: "Regulatory Library", href: "/library" }, { label: "Knowledge graph" }]}
      />
      {!res.ok ? <ErrorPanel message={res.error} /> : <KnowledgeGraph graph={res.data} />}
    </>
  );
}
