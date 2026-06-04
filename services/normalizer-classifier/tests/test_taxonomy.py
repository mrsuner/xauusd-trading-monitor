from __future__ import annotations

from normalizer_classifier.taxonomy import CategoryOption, TagOption, TaxonomyContext, normalize_category, normalize_topic_tags


def test_normalize_category_uses_controlled_dictionary() -> None:
    context = TaxonomyContext(categories=[CategoryOption(key="diplomacy", label_en="Diplomacy")])

    assert normalize_category("Diplomacy", context) == "diplomacy"
    assert normalize_category("regional_security", context) == "other"


def test_normalize_topic_tags_uses_aliases_and_slugs() -> None:
    context = TaxonomyContext(
        tags=[
            TagOption(key="united-states", label="United States", aliases=("usa", "u.s.", "U.S.A.")),
            TagOption(key="nuclear", label="Nuclear", aliases=("uranium enrichment",)),
        ]
    )

    assert normalize_topic_tags(["U.S.", "Uranium enrichment", "IRGC / Navy"], context) == [
        "united-states",
        "nuclear",
        "irgc-navy",
    ]
