"""File-backed content store for learning topics and the regulatory library.

Content is authored in YAML under ``backend/content/`` so it is reviewable in git.
Phase 1 loads it into memory at startup; Phase 2 adds the PostgreSQL load (same shapes).
A content lint runs at load time: every regulatory reference on a topic must resolve to a
known provision or chapter, and every exercise must point to a registered calculation.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from risklab_engine.calcs import REGISTRY

CONTENT_DIR = Path(__file__).resolve().parents[2] / "content"
BIS_CHAPTER_URL = "https://www.bis.org/basel_framework/chapter/{std}/{num}.htm"

SECTION_KEYS = ("concept", "why_it_matters", "real_world_example", "mathematical_logic",
                "variables", "worked_example", "related_concepts")


class ContentError(RuntimeError):
    pass


def _load_yaml(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def chapter_url(code: str) -> str:
    m = re.fullmatch(r"([A-Z]+)(\d+)", code)
    if not m:
        raise ContentError(f"bad chapter code {code!r}")
    return BIS_CHAPTER_URL.format(std=m.group(1), num=m.group(2))


def provision_url(prov_id: str) -> str:
    chapter, para = prov_id.split(".", 1)
    return chapter_url(chapter) + f"#paragraph_{chapter}_{para}" if para else chapter_url(chapter)


class ContentStore:
    def __init__(self, root: Path = CONTENT_DIR) -> None:
        self.root = root
        self.paths: list[dict[str, Any]] = []
        self.topics: dict[str, dict[str, Any]] = {}
        self.chapters: dict[str, dict[str, Any]] = {}
        self.provisions: dict[str, dict[str, Any]] = {}
        self._load_regulatory()
        self._load_learn()
        self._lint()

    # ---------------------------------------------------------------- regulatory
    def _load_regulatory(self) -> None:
        reg = _load_yaml(self.root / "regulatory" / "chapters.yaml")
        for ch in reg["chapters"]:
            ch = dict(ch)
            ch.setdefault("source_url", chapter_url(ch["code"]))
            ch["provisions"] = []
            self.chapters[ch["code"]] = ch
        for f in sorted((self.root / "regulatory" / "provisions").glob("*.yaml")):
            p = _load_yaml(f)
            pid = p["id"]
            if "." not in pid:
                raise ContentError(f"{f.name}: provision id must look like MAR33.4")
            code = pid.split(".")[0]
            if code not in self.chapters:
                raise ContentError(f"{f.name}: unknown chapter {code}")
            p.setdefault("source_url", provision_url(pid))
            p.setdefault("effective_date", self.chapters[code]["effective_date"])
            p.setdefault("last_update", self.chapters[code]["last_update"])
            p.setdefault("version_tag", self.chapters[code].get("version_tag", "MAR-2023-01"))
            p["chapter_code"] = code
            p["chapter_title"] = self.chapters[code]["title"]
            self.provisions[pid] = p
            self.chapters[code]["provisions"].append({"id": pid, "title": p["title"]})
        for ch in self.chapters.values():
            ch["provisions"].sort(key=lambda x: _para_sort_key(x["id"]))

    # ---------------------------------------------------------------- learn
    def _load_learn(self) -> None:
        syllabus = _load_yaml(self.root / "learn" / "syllabus.yaml")
        files = {f.stem: f for f in (self.root / "learn" / "topics").glob("*.yaml")}
        for path in syllabus["paths"]:
            entry = {k: path[k] for k in ("slug", "title", "level", "ordinal", "description")}
            entry["topics"] = []
            for i, t in enumerate(path["topics"], start=1):
                slug = t["slug"]
                authored = slug in files
                entry["topics"].append({"slug": slug, "title": t["title"], "level": t.get("level", path["level"]),
                                        "ordinal": i, "authored": authored})
                if authored:
                    topic = _load_yaml(files.pop(slug))
                    topic["slug"] = slug
                    topic["path_slug"] = path["slug"]
                    topic.setdefault("level", t.get("level", path["level"]))
                    self.topics[slug] = topic
            self.paths.append(entry)
        if files:
            raise ContentError(f"topic files not in syllabus: {sorted(files)}")

    # ---------------------------------------------------------------- lint
    def _lint(self) -> None:
        for slug, t in self.topics.items():
            missing = [k for k in SECTION_KEYS if k not in t.get("sections", {})]
            if missing:
                raise ContentError(f"topic {slug}: missing sections {missing}")
            if not t.get("questions") or len(t["questions"]) < 3:
                raise ContentError(f"topic {slug}: needs at least 3 knowledge-check questions")
            for ref in t.get("regulatory_references", []):
                self._resolve_ref(ref["id"], f"topic {slug}")
            ex = t.get("exercise")
            if ex and ex["calc_id"] not in REGISTRY:
                raise ContentError(f"topic {slug}: unknown exercise calc {ex['calc_id']}")
            for rel in t["sections"].get("related_concepts", []):
                rel["authored"] = rel["slug"] in self.topics
        for pid, p in self.provisions.items():
            for x in p.get("cross_references", []):
                self._resolve_ref(x["id"], f"provision {pid}")
            for c in p.get("related_calculations", []):
                if c["calc_id"] not in REGISTRY:
                    raise ContentError(f"provision {pid}: unknown calc {c['calc_id']}")
                c.setdefault("title", REGISTRY[c["calc_id"]].title)
            for tpc in p.get("related_topics", []):
                tpc["authored"] = tpc["slug"] in self.topics
                if tpc["authored"]:
                    tpc.setdefault("title", self.topics[tpc["slug"]]["title"])

    def _resolve_ref(self, ref_id: str, where: str) -> None:
        code = ref_id.split(".")[0]
        if ref_id not in self.provisions and code not in self.chapters:
            raise ContentError(f"{where}: regulatory reference {ref_id} does not resolve to a known provision or chapter")

    # ---------------------------------------------------------------- queries
    def ref_card(self, ref_id: str) -> dict[str, Any]:
        if ref_id in self.provisions:
            p = self.provisions[ref_id]
            return {"id": ref_id, "title": p["title"], "url": p["source_url"], "chapter_code": p["chapter_code"], "in_library": True}
        ch = self.chapters[ref_id.split(".")[0]]
        return {"id": ref_id, "title": ch["title"], "url": ch["source_url"], "chapter_code": ch["code"], "in_library": False}

    def topic_payload(self, slug: str) -> dict[str, Any] | None:
        t = self.topics.get(slug)
        if not t:
            return None
        out = {k: v for k, v in t.items() if k != "regulatory_references"}
        out["regulatory_references"] = [self.ref_card(r["id"]) | {"note": r.get("note")} for r in t.get("regulatory_references", [])]
        return out

    def chapter_list(self) -> list[dict[str, Any]]:
        return [{k: v for k, v in ch.items() if k != "provisions"} | {"provision_count": len(ch["provisions"])}
                for ch in sorted(self.chapters.values(), key=lambda c: c["code"])]

    def provision_payload(self, pid: str) -> dict[str, Any] | None:
        p = self.provisions.get(pid)
        if not p:
            return None
        out = dict(p)
        out["cross_references"] = [self.ref_card(x["id"]) | {"relation": x.get("relation", "see also")} for x in p.get("cross_references", [])]
        return out

    def search(self, q: str, limit: int = 20) -> list[dict[str, Any]]:
        q = q.strip().lower()
        if not q:
            return []
        hits = []
        for pid, p in self.provisions.items():
            hay = " ".join(str(p.get(k, "")) for k in ("title", "excerpt", "plain_language", "technical_interpretation")).lower()
            if q in hay or q in pid.lower():
                idx = hay.find(q)
                snippet = hay[max(0, idx - 80): idx + 120].strip() if idx >= 0 else p.get("title", "")
                hits.append({"id": pid, "chapter_code": p["chapter_code"], "title": p["title"], "snippet": "…" + snippet + "…"})
        for code, ch in self.chapters.items():
            if q in ch["title"].lower() or q in code.lower() or q in ch.get("summary", "").lower():
                hits.append({"id": code, "chapter_code": code, "title": ch["title"], "snippet": ch.get("summary", "")})
        return hits[:limit]

    def graph(self) -> dict[str, Any]:
        nodes: dict[str, dict[str, Any]] = {}
        edges: list[dict[str, str]] = []

        def node(nid: str, kind: str, label: str, href: str) -> None:
            nodes.setdefault(nid, {"id": nid, "kind": kind, "label": label, "href": href})

        for code, ch in self.chapters.items():
            node(f"reg:{code}", "regulation", f"{code} · {ch['title']}", f"/library/{code}")
        for pid, p in self.provisions.items():
            node(f"reg:{pid}", "regulation", f"{pid} · {p['title']}", f"/library/{p['chapter_code']}/{pid}")
            edges.append({"from": f"reg:{p['chapter_code']}", "to": f"reg:{pid}", "relation": "contains"})
            for x in p.get("cross_references", []):
                node(f"reg:{x['id']}", "regulation", x["id"], f"/library/{x['id'].split('.')[0]}" + (f"/{x['id']}" if "." in x["id"] else ""))
                edges.append({"from": f"reg:{pid}", "to": f"reg:{x['id']}", "relation": x.get("relation", "see also")})
            for c in p.get("related_calculations", []):
                node(f"calc:{c['calc_id']}", "calculation", c["title"], f"/calc/{c['calc_id']}")
                edges.append({"from": f"reg:{pid}", "to": f"calc:{c['calc_id']}", "relation": "implemented by"})
            for tpc in p.get("related_topics", []):
                if tpc["authored"]:
                    node(f"topic:{tpc['slug']}", "module", tpc["title"], f"/learn/{tpc['slug']}")
                    edges.append({"from": f"topic:{tpc['slug']}", "to": f"reg:{pid}", "relation": "explains"})
        for slug, t in self.topics.items():
            node(f"topic:{slug}", "module", t["title"], f"/learn/{slug}")
            for r in t.get("regulatory_references", []):
                nid = f"reg:{r['id']}"
                if nid in nodes:
                    edges.append({"from": f"topic:{slug}", "to": nid, "relation": "cites"})
            if t.get("exercise"):
                cid = t["exercise"]["calc_id"]
                node(f"calc:{cid}", "calculation", REGISTRY[cid].title, f"/calc/{cid}")
                edges.append({"from": f"topic:{slug}", "to": f"calc:{cid}", "relation": "exercise"})
            for rel in t["sections"].get("related_concepts", []):
                if rel["authored"]:
                    edges.append({"from": f"topic:{slug}", "to": f"topic:{rel['slug']}", "relation": "related"})
        # de-duplicate edges
        seen, uniq = set(), []
        for e in edges:
            key = (e["from"], e["to"], e["relation"])
            if key not in seen:
                seen.add(key)
                uniq.append(e)
        return {"nodes": list(nodes.values()), "edges": uniq}


def _para_sort_key(pid: str) -> tuple[str, float]:
    code, _, para = pid.partition(".")
    try:
        return code, float(para)
    except ValueError:
        return code, 0.0


@lru_cache(maxsize=1)
def get_store() -> ContentStore:
    return ContentStore()
