import pytest

from agent.settings import Settings, get_settings


def test_every_node_gets_a_real_model():
    s = get_settings()
    for name in s["nodes"]:
        assert s.node(name)["model_name"]


def test_cheap_nodes_use_small_model_and_writer_uses_strong():
    s = get_settings()
    models = s.profile["models"]
    assert s.node("risk")["model_name"] == models["small"]
    assert s.node("writer")["model_name"] == models["strong"]


def test_embeddings_are_the_same_open_model_in_both_profiles():
    p = get_settings()["profiles"]
    assert p["open"]["embeddings"] == p["paid"]["embeddings"]
    assert p["open"]["reranker"] == p["paid"]["reranker"]


def test_auto_send_can_never_be_switched_on():
    raw = dict(get_settings().raw)
    raw["autonomy"] = {"auto_skip_low_fit": True, "auto_send": True}
    with pytest.raises(ValueError):
        Settings(raw)


def test_env_switches_marketplace(monkeypatch):
    monkeypatch.setenv("GIGBID_MARKETPLACE", "upwork")
    assert Settings(get_settings().raw).marketplace == "upwork"
