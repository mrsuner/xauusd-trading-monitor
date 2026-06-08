from __future__ import annotations

from datetime import datetime, timezone

from tickbase_anomaly_consumer.mapping import (
    SeverityThresholds,
    change_ratio,
    classify_severity,
    instrument_label,
    map_anomaly,
    window_label,
)
from tickbase_anomaly_consumer.models import AnomalyEvent

THRESHOLDS = SeverityThresholds(s_multiplier=3.0, a_multiplier=2.0, b_multiplier=1.5)


def make_event(**overrides) -> AnomalyEvent:
    base = dict(
        id=1,
        rule_id="gold-1m-10usd",
        asset_class="metal",
        base="XAU",
        quote="USD",
        direction="up",
        metric="abs",
        window_secs=60,
        threshold=10.0,
        change_abs=15.0,
        change_pct=0.6,
        value_start=2400.0,
        value_end=2415.0,
        obs_count=5,
        window_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        triggered_at=datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc),
    )
    base.update(overrides)
    return AnomalyEvent(**base)


def test_change_ratio_uses_metric():
    assert change_ratio(make_event(metric="abs", change_abs=15, threshold=10)) == 1.5
    assert change_ratio(make_event(metric="pct", change_pct=2.0, threshold=0.5)) == 4.0


def test_change_ratio_zero_threshold_is_safe():
    assert change_ratio(make_event(threshold=0.0)) == 1.0


def test_classify_severity_bands():
    assert classify_severity(make_event(change_abs=35, threshold=10), THRESHOLDS) == "S"  # 3.5x
    assert classify_severity(make_event(change_abs=25, threshold=10), THRESHOLDS) == "A"  # 2.5x
    assert classify_severity(make_event(change_abs=16, threshold=10), THRESHOLDS) == "B"  # 1.6x
    assert classify_severity(make_event(change_abs=11, threshold=10), THRESHOLDS) == "C"  # 1.1x


def test_severity_uses_absolute_value_for_down_moves():
    event = make_event(direction="down", change_abs=-30.0, threshold=10.0)
    assert classify_severity(event, THRESHOLDS) == "S"


def test_public_only_for_s_and_a():
    assert map_anomaly(make_event(change_abs=35, threshold=10), THRESHOLDS).to_public is True  # S
    assert map_anomaly(make_event(change_abs=25, threshold=10), THRESHOLDS).to_public is True  # A
    assert map_anomaly(make_event(change_abs=16, threshold=10), THRESHOLDS).to_public is False  # B
    assert map_anomaly(make_event(change_abs=11, threshold=10), THRESHOLDS).to_public is False  # C


def test_instrument_and_window_labels():
    assert instrument_label(make_event()) == "黃金 (XAU/USD)"
    assert instrument_label(make_event(asset_class="fx", base="USD", quote="EUR")) == "USD/EUR"
    assert window_label(60) == "1 分鐘"
    assert window_label(45) == "45 秒"
    assert window_label(7200) == "2 小時"


def test_map_anomaly_summary_and_relevance():
    mapped = map_anomaly(make_event(change_abs=35, threshold=10), THRESHOLDS)
    assert mapped.severity == "S"
    assert mapped.relevance_score == 95
    assert "黃金 (XAU/USD)" in mapped.summary_zh
    assert "上漲" in mapped.summary_zh
    assert "market_anomaly" in mapped.topic_tags
    assert mapped.alert_message.startswith("[S]")
