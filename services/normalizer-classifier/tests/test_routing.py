from __future__ import annotations

from normalizer_classifier.routing import DomainKeyword, DomainOption, RoutingContext


def domain(
    key: str,
    *,
    keywords: tuple[DomainKeyword, ...],
    threshold: int = 30,
    prior: int = 0,
) -> DomainOption:
    return DomainOption(
        key=key,
        threshold=threshold,
        sort_order=10,
        prompt_body=f"{key} lens",
        keywords=keywords,
        prior_weight=prior,
    )


def test_router_deduplicates_aliases_within_a_group() -> None:
    context = RoutingContext(
        domains=(
            domain(
                "monetary",
                keywords=(
                    DomainKeyword("fed", "fed", 30, "word"),
                    DomainKeyword("fed", "federal reserve", 30, "substring"),
                    DomainKeyword("inflation", "inflation", 10, "substring"),
                ),
            ),
        )
    )
    decision = context.route("The Fed and Federal Reserve discussed inflation.")
    assert decision.scores == {"monetary": 40}
    assert decision.matched_groups == {"monetary": ("fed", "inflation")}


def test_router_requires_content_even_with_source_prior() -> None:
    context = RoutingContext(
        domains=(
            domain(
                "energy",
                keywords=(DomainKeyword("oil", "oil", 30, "word"),),
                prior=10,
            ),
        )
    )
    assert context.route("Routine schedule update").passed is False
    assert context.route("Oil supply update").scores == {"energy": 40}


def test_router_uses_deterministic_ties_and_top_two() -> None:
    context = RoutingContext(
        domains=tuple(
            domain(key, keywords=(DomainKeyword(key, "shared", 30),))
            for key in ("monetary", "geopolitics", "energy")
        ),
        top_k=2,
    )
    decision = context.route("shared")
    assert decision.matched_domains == ("energy", "geopolitics", "monetary")
    assert decision.selected_domains == ("energy", "geopolitics")


def test_word_matching_does_not_match_inside_another_word() -> None:
    context = RoutingContext(
        domains=(
            domain("monetary", keywords=(DomainKeyword("fed", "fed", 30, "word"),)),
        )
    )
    assert context.route("federalism debate").passed is False
    assert context.route("Fed decision").passed is True


def test_config_version_is_stable_and_changes_with_configuration() -> None:
    base = RoutingContext(
        domains=(domain("energy", keywords=(DomainKeyword("oil", "oil", 30),)),)
    )
    same = RoutingContext(domains=tuple(reversed(base.domains)))
    changed = RoutingContext(
        domains=(domain("energy", keywords=(DomainKeyword("oil", "oil", 10),)),)
    )
    assert base.config_version == same.config_version
    assert base.config_version != changed.config_version
    assert base.snapshot_payload["top_k"] == 2
