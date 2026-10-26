from public_syncer.db import raw_item_translations_select_sql
from public_syncer.payload import build_raw_item_payload
from test_payload import make_raw_item


def test_summary_only_survives_public_selection_and_payload():
    item = make_raw_item()
    item.translation_status = "summary_only"
    for translation in item.translations:
        translation.status = "summary_only"
        translation.full_translation = None
    payload = build_raw_item_payload(item, max_original_chars=4000, max_translation_chars=8000,
                                    sync_languages=("zh-Hant", "en", "ja"))
    assert len(payload["translations"]) == 3
    for translation in payload["translations"]:
        assert translation["status"] == "summary_only"
        assert translation["summary"]
        assert translation["full_translation"] is None
        assert not translation["is_truncated"]
    assert "'summary_only'" in raw_item_translations_select_sql()
