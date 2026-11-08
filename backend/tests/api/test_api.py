"""Endpoint tests against the live content store (also acts as the content lint in CI)."""
import pytest
from fastapi.testclient import TestClient

from risklab_api.main import app
from risklab_api.services.content import get_store

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_paths_and_every_authored_topic_loads():
    paths = client.get("/api/learn/paths").json()
    assert len(paths) == 6
    authored = [t["slug"] for p in paths for t in p["topics"] if t["authored"]]
    assert authored
    for slug in authored:
        t = client.get(f"/api/learn/topics/{slug}").json()
        assert set(t["sections"]) >= {"concept", "why_it_matters", "real_world_example", "mathematical_logic", "variables", "worked_example", "related_concepts"}
        assert 3 <= len(t["questions"]) <= 5
        for q in t["questions"]:
            assert 0 <= q["answer_index"] < len(q["choices"])
        for ref in t["regulatory_references"]:
            assert ref["url"].startswith("https://www.bis.org/")


def test_unauthored_topic_is_404():
    assert client.get("/api/learn/topics/monte-carlo-simulation").status_code == 404


def test_chapters_and_provisions():
    chapters = client.get("/api/regulatory/chapters").json()
    codes = {c["code"] for c in chapters}
    assert {"MAR10", "MAR11", "MAR12", "MAR20", "MAR21", "MAR22", "MAR23", "MAR30", "MAR31", "MAR32", "MAR33", "RBC25"} <= codes
    mar33 = client.get("/api/regulatory/chapters/mar33").json()
    assert mar33["provisions"][0]["id"] == "MAR33.2"
    p = client.get("/api/regulatory/provisions/MAR33.3").json()
    assert p["excerpt_kind"] == "quote" and "97.5" in p["excerpt"]
    assert client.get("/api/regulatory/provisions/MAR99.1").status_code == 404


def test_search_and_graph():
    hits = client.get("/api/regulatory/search", params={"q": "liquidity horizon"}).json()
    assert any(h["id"] == "MAR33.4" for h in hits)
    g = client.get("/api/regulatory/graph").json()
    ids = {n["id"] for n in g["nodes"]}
    assert all(e["from"] in ids and e["to"] in ids for e in g["edges"])


def test_calc_list_and_run():
    calcs = client.get("/api/calc").json()
    assert {c["id"] for c in calcs} >= {"var_es_historical", "liquidity_horizon_scaling"}
    r = client.post("/api/calc/liquidity_horizon_scaling", json={"es_base": 100, "es_lh20": 100, "es_lh40": 100, "es_lh60": 100, "es_lh120": 100})
    assert r.status_code == 200
    assert r.json()["result"]["uplift_vs_base"] == pytest.approx(12 ** 0.5)
    assert client.post("/api/calc/var_es_historical", json={"confidence": 2}).status_code == 422
    assert client.post("/api/calc/does_not_exist", json={}).status_code == 404


def test_content_lint_passed_at_import():
    store = get_store()
    assert store.topics and store.provisions
