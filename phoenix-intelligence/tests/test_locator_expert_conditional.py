import json
from types import SimpleNamespace

from services.agents.locator_expert import LocatorExpertAgent
from services.cache import Cache
from api.models import LocatorDiscoveryRequest, LocatorDiscoveryResponse


class KnowledgeStub:
    def get_context_for_agent(self, *_args, **_kwargs):
        return ""


class LLMStub:
    settings = SimpleNamespace(provider="anthropic", model="claude-test")

    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def generate(self, system_prompt, user_prompt):
        self.calls.append((system_prompt, user_prompt))
        if self.error:
            raise self.error
        return json.dumps(self.response)


def test_strict_conditional_mode_does_not_return_heuristics_without_llm():
    agent = LocatorExpertAgent(KnowledgeStub(), Cache(), llm_client=None)
    result = agent.process({
        "page_url": "https://example.test",
        "element_name": "Submit",
        "element_context": {"element_identity": "dom:submit"},
        "require_llm": True,
    })
    assert result["locators"] == []
    assert result["recommended_locator"] is None
    assert result["metadata"]["strict_conditional_fallback"] is True


def test_scoped_evidence_is_sent_to_llm_and_metadata_is_returned():
    llm = LLMStub({
        "locators": [{"strategy": "role", "value": "button[name='Submit']"}]
    })
    agent = LocatorExpertAgent(KnowledgeStub(), Cache(), llm_client=llm)
    context = {
        "element_identity": "dom:submit",
        "fallback_reasons": ["ambiguous"],
        "attempted_locators": [{"locator_value": ".button", "match_count": 3}],
    }
    result = agent.process({
        "page_url": "https://example.test",
        "element_name": "Submit",
        "element_context": context,
        "require_llm": True,
    })
    assert len(llm.calls) == 1
    assert '"element_identity": "dom:submit"' in llm.calls[0][1]
    assert '"match_count": 3' in llm.calls[0][1]
    assert result["metadata"]["provider"] == "anthropic"
    assert result["metadata"]["model"] == "claude-test"


def test_strict_conditional_mode_stays_unresolved_when_llm_fails():
    llm = LLMStub(error=RuntimeError("provider unavailable"))
    agent = LocatorExpertAgent(KnowledgeStub(), Cache(), llm_client=llm)
    result = agent.process({
        "page_url": "https://example.test",
        "element_name": "Submit",
        "require_llm": True,
    })
    assert result["locators"] == []


def test_legacy_mode_keeps_existing_heuristic_fallback():
    agent = LocatorExpertAgent(KnowledgeStub(), Cache(), llm_client=None)
    result = agent.process({
        "page_url": "https://example.test",
        "element_name": "Submit",
    })
    assert len(result["locators"]) == 2
    assert result["locators"][0]["strategy"] == "role"


def test_api_models_accept_context_only_request_and_preserve_identity():
    request = LocatorDiscoveryRequest(
        page_url="https://example.test",
        element_contexts=[{"element_name": "Submit", "element_identity": "dom:submit"}],
        require_llm=True,
    )
    response = LocatorDiscoveryResponse(
        locators=[{
            "element_name": "Submit",
            "element_identity": "dom:submit",
            "strategy": "css",
            "value": "#submit",
        }]
    )

    assert request.elements == []
    assert request.require_llm is True
    assert response.locators[0].element_identity == "dom:submit"
    assert response.locators[0].value == "#submit"
