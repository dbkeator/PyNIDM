"""Tests for nidm_queryai helpers that don't require an AI/API call."""

from __future__ import annotations
from pathlib import Path
from nidm.experiment.tools.nidm_queryai import _extract_data_elements


def test_extract_data_elements_captures_value_levels(tmp_path: Path) -> None:
    """A DataElement whose value levels are defined in the data (via
    reproschema:choices -> value/label) is captured as a coded->label dict;
    a DataElement with no level definitions has no 'levels' key.  This is what
    licenses queryai to translate coded values (and refuse when absent)."""
    ttl = """
@prefix niiri: <http://iri.nidash.org/> .
@prefix nidm: <http://purl.org/nidash/nidm#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix reproschema: <http://schema.repronim.org/> .

niiri:SEX_withlevels a nidm:PersonalDataElement ;
    rdfs:label "SEX" ;
    reproschema:choices [ reproschema:value "1" ; rdfs:label "Male" ] ,
                        [ reproschema:value "2" ; rdfs:label "Female" ] .

niiri:DX_nolevels a nidm:PersonalDataElement ;
    rdfs:label "diagnostic group" .
"""
    cde = tmp_path / "cde.ttl"
    cde.write_text(ttl, encoding="utf-8")

    data_elements, _g = _extract_data_elements([str(cde)])
    by_uri = {d["uri"]: d for d in data_elements}

    sex = by_uri["http://iri.nidash.org/SEX_withlevels"]
    dx = by_uri["http://iri.nidash.org/DX_nolevels"]

    assert sex.get("levels") == {"1": "Male", "2": "Female"}
    # No level definitions -> no 'levels' key -> queryai must not fabricate a mapping
    assert "levels" not in dx


def test_get_provider_selects_local_llama(monkeypatch) -> None:
    """A configured local LLaMA server (PYNIDM_LLAMA_URL) selects the 'llama'
    provider when no cloud key is present; an explicit PYNIDM_AI_PROVIDER wins."""
    from nidm.experiment.tools.nidm_queryai import _get_provider

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("PYNIDM_AI_PROVIDER", raising=False)
    monkeypatch.setenv("PYNIDM_LLAMA_URL", "http://localhost:8080/v1")
    assert _get_provider() == "llama"

    monkeypatch.setenv("PYNIDM_AI_PROVIDER", "anthropic")
    assert _get_provider() == "anthropic"


def test_query_llama_posts_openai_format_and_parses(monkeypatch) -> None:
    """_query_llama POSTs an OpenAI chat payload to <url>/chat/completions and
    returns choices[0].message.content (no API key, no real server)."""
    from nidm.experiment.tools import nidm_queryai as q

    captured = {}

    class _FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "SELECT * WHERE {}"}}]}

    def _fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["payload"] = json
        return _FakeResp()

    monkeypatch.setattr(q.requests, "post", _fake_post)

    out = q._query_llama("SYS_PROMPT", "USER_QUESTION")
    assert out == "SELECT * WHERE {}"
    assert captured["url"].endswith("/chat/completions")
    msgs = captured["payload"]["messages"]
    assert msgs[0]["role"] == "system" and msgs[0]["content"] == "SYS_PROMPT"
    assert msgs[1]["role"] == "user" and msgs[1]["content"] == "USER_QUESTION"


def test_get_api_key_is_provider_aware(monkeypatch) -> None:
    """The provider-specific key is selected even when both are set, so
    PYNIDM_AI_PROVIDER=openai uses OPENAI_API_KEY (not the Anthropic key)."""
    from nidm.experiment.tools.nidm_queryai import _get_api_key

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-xxx")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-oai-yyy")
    assert _get_api_key("openai") == "sk-oai-yyy"
    assert _get_api_key("anthropic") == "sk-ant-xxx"
    assert _get_api_key("llama") is None
