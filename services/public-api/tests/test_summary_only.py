import pytest

from public_api.models import PublicRawItemTranslationInput


def test_summary_only_retains_explicit_scope_without_full_text():
    value = PublicRawItemTranslationInput(language="zh-Hant", summary="新聞摘要", status="summary_only")
    assert value.model_dump()["status"] == "summary_only"
    assert value.full_translation is None


@pytest.mark.parametrize("summary,full", [(None, None), ("摘要", "不應提供的全文")])
def test_summary_only_rejects_missing_summary_or_claimed_full_translation(summary, full):
    with pytest.raises(ValueError, match="summary_only"):
        PublicRawItemTranslationInput(language="zh-Hant", summary=summary, full_translation=full, status="summary_only")
