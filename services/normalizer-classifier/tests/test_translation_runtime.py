"""Worker-path regression tests: paid calls are mocked and no data is backfilled."""
import json

import pytest

from normalizer_classifier.model_client import ModelClientError, build_translation_model_clients, validate_auxiliary_text_result
from normalizer_classifier.models import AuxiliaryTextResult
from normalizer_classifier.settings import Settings
from test_model_client import make_objects


def result():
    return AuxiliaryTextResult.model_validate({"translations": [
        {"language": "zh-Hant", "summary": "據報有168名兒童及教師遇難。", "full_translation": "據報有168名兒童及教師遇難。"},
        {"language": "en", "summary": "Reportedly, 168 children and teachers died.", "full_translation": "Reportedly, 168 children and teachers died."},
        {"language": "th", "summary": "มีรายงานว่าเด็กและครู 168 คนเสียชีวิต", "full_translation": "มีรายงานว่าเด็กและครู 168 คนเสียชีวิต"},
        {"language": "ja", "summary": "子供と教師168人が死亡したと報じられた。", "full_translation": "子供と教師168人が死亡したと報じられた。"},
    ]})


@pytest.mark.parametrize("failure", ["duplicate", "wrong_thai", "wrong_chinese", "long_summary", "missing_full"])
def test_worker_rejects_invalid_translations(failure):
    value = result()
    if failure == "duplicate":
        value.translations.append(value.translations[0])
    elif failure == "wrong_thai":
        value.translations[2].full_translation = "English source copied unchanged."
    elif failure == "wrong_chinese":
        value.translations[0].summary = "English summary."
    elif failure == "long_summary":
        value.translations[0].summary = "中" * 281
    else:
        value.translations[3].full_translation = None
    with pytest.raises(ValueError):
        validate_auxiliary_text_result(value, languages=("zh-Hant", "en", "th", "ja"),
                                      require_all_languages=True, full_translation_required=True)


@pytest.mark.parametrize("finish,refusal", [("stop", None), ("length", None), ("stop", "Refused")])
async def test_runtime_120b_price_routing_and_failure_usage(monkeypatch, finish, refusal):
    settings = Settings(DATABASE_URL="postgresql://test:test@localhost/test", TRANSLATION_MODEL_API_KEY="test-key", TRANSLATION_PRIMARY_MODEL_NAME="openai/gpt-oss-120b",
        TRANSLATION_PAID_FALLBACK_ENABLED=False, TRANSLATION_OUTPUT_LANGUAGES="zh-Hant,en,th,ja",
        TRANSLATION_MODEL_REASONING_EFFORT="low", TRANSLATION_MODEL_RESPONSE_FORMAT="json_schema")
    client, = build_translation_model_clients(settings)

    async def fake_post(payload, **kwargs):
        assert payload["model"] == "openai/gpt-oss-120b"
        assert payload["provider"] == {"sort": "price", "require_parameters": True,
                                        "max_price": {"prompt": 0.03, "completion": 0.17}}
        assert payload["reasoning_effort"] == "low"
        assert "parenthetical locations" in payload["messages"][0]["content"]
        return {"choices": [{"finish_reason": finish, "message": {
            "content": json.dumps(result().model_dump()), "refusal": refusal}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 100}}

    monkeypatch.setattr(client, "_post_chat_completions", fake_post)
    if finish == "stop" and not refusal:
        response = await client.summarize_and_translate(*make_objects())
        assert len(response.result.translations) == 4
    else:
        with pytest.raises(ModelClientError, match="incomplete or refused") as caught:
            await client.summarize_and_translate(*make_objects())
        assert caught.value.usage is not None
        assert caught.value.usage.success is False


@pytest.mark.parametrize("price", [-1, 0, float("inf"), float("nan")])
def test_price_cap_must_be_positive_finite(price):
    with pytest.raises(ValueError):
        Settings(DATABASE_URL="postgresql://test:test@localhost/test", TRANSLATION_MAX_PROMPT_PRICE=price)
