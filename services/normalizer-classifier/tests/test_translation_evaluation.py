import json

import pytest

from normalizer_classifier.translation_evaluation import LANGUAGES, MODELS, OBSERVED_IDS, build_payload, lexical_flags, local_cases, validate_translation


def case():
    return {"source_name": "Test", "title": None, "content": "168 children", "language": "en",
            "source_url": "https://example.com", "published_at": "2026-09-27T00:00:00Z"}


def body():
    result = {"translations": [{"language": lang, "summary": "Summary", "full_translation": "Full"}
                              for lang in LANGUAGES], "detected_language": "en", "notes": None}
    return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(result)}}]}


def test_only_model_changes_in_ab_payload():
    left, right = [build_payload(case(), model) for model in MODELS]
    assert left.pop("model") != right.pop("model")
    assert left == right
    assert left["reasoning"]["effort"] == "low"
    assert left["provider"] == {
        "sort": "price", "require_parameters": True,
        "max_price": {"prompt": 0.15, "completion": 0.6},
    }
    assert "stored_translations" not in left["messages"][1]["content"]


def test_explicit_locale_prompt_is_isolated_to_evaluation_variant():
    original = build_payload(case(), MODELS[0])
    clarified = build_payload(case(), MODELS[0], prompt_variant="explicit-locales")
    assert "ONLY the en" not in original["messages"][0]["content"]
    assert "ONLY the en" in clarified["messages"][0]["content"]
    assert original["messages"][1] == clarified["messages"][1]
    with pytest.raises(ValueError, match="variant"):
        build_payload(case(), MODELS[0], prompt_variant="unknown")


@pytest.mark.parametrize("failure", ["truncated", "duplicate_locale", "missing_full", "long_summary"])
def test_reject_invalid_translation_contract(failure):
    data = body()
    value = json.loads(data["choices"][0]["message"]["content"])
    if failure == "truncated":
        data["choices"][0]["finish_reason"] = "length"
    elif failure == "duplicate_locale":
        value["translations"][0]["language"] = "en"
    elif failure == "missing_full":
        value["translations"][0]["full_translation"] = None
    else:
        value["translations"][0]["summary"] = "x" * 281
    data["choices"][0]["message"]["content"] = json.dumps(value)
    with pytest.raises(ValueError):
        validate_translation(data)


def test_review_flags_preserve_counts_scripts_and_source_entity():
    assert lexical_flags("168 children", "198 children", "en", case_id=OBSERVED_IDS[0])
    assert lexical_flags("168 children", "168 children", "th", case_id=OBSERVED_IDS[0]) == ["missing_target_script"]
    assert "observed_unsupported_iran_entity" in lexical_flags("ICC sanctions", "Sanctions on Iran", "en", case_id=OBSERVED_IDS[1])
    assert lexical_flags("168 children", "168名兒童", "zh-Hant", case_id=OBSERVED_IDS[0]) == []


def test_local_snapshot_nested_json_is_not_line_split(monkeypatch):
    from types import SimpleNamespace
    cases = [case() | {"id": value, "stored_translations": [{"language": "en"}]} for value in OBSERVED_IDS]
    monkeypatch.setattr("normalizer_classifier.translation_evaluation.subprocess.run",
                        lambda *args, **kwargs: SimpleNamespace(stdout=json.dumps(cases, indent=2)))
    assert local_cases() == cases
