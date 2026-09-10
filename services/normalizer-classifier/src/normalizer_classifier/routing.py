from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field


@dataclass(frozen=True)
class DomainKeyword:
    group_key: str
    term: str
    weight: int
    match_type: str = "substring"


@dataclass(frozen=True)
class DomainOption:
    key: str
    threshold: int
    sort_order: int
    prompt_body: str
    keywords: tuple[DomainKeyword, ...] = ()
    prior_weight: int = 0


@dataclass(frozen=True)
class RoutingDecision:
    scores: dict[str, int] = field(default_factory=dict)
    matched_domains: tuple[str, ...] = ()
    selected_domains: tuple[str, ...] = ()
    matched_groups: dict[str, tuple[str, ...]] = field(default_factory=dict)
    config_version: str = ""

    @property
    def passed(self) -> bool:
        return bool(self.matched_domains)


@dataclass(frozen=True)
class RoutingContext:
    domains: tuple[DomainOption, ...] = ()
    top_k: int = 2

    @property
    def snapshot_payload(self) -> dict[str, object]:
        return {
            "top_k": self.top_k,
            "domains": [
                {
                    "key": domain.key,
                    "threshold": domain.threshold,
                    "sort_order": domain.sort_order,
                    "prompt_body": domain.prompt_body,
                    "prior_weight": domain.prior_weight,
                    "keywords": [
                        {
                            "group_key": keyword.group_key,
                            "term": keyword.term,
                            "weight": keyword.weight,
                            "match_type": keyword.match_type,
                        }
                        for keyword in sorted(
                            domain.keywords,
                            key=lambda item: (item.group_key, item.term, item.weight, item.match_type),
                        )
                    ],
                }
                for domain in sorted(self.domains, key=lambda item: item.key)
            ],
        }

    @property
    def config_version(self) -> str:
        canonical = json.dumps(self.snapshot_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def route(self, text: str) -> RoutingDecision:
        normalized_text = unicodedata.normalize("NFKC", text).casefold()
        ranked: list[tuple[str, int]] = []
        matched_groups: dict[str, tuple[str, ...]] = {}

        for domain in self.domains:
            group_weights: dict[str, int] = {}
            for keyword in domain.keywords:
                if _matches(normalized_text, keyword):
                    group_weights[keyword.group_key] = max(
                        group_weights.get(keyword.group_key, 0),
                        keyword.weight,
                    )
            if not group_weights:
                continue
            score = min(100, sum(group_weights.values()) + domain.prior_weight)
            if score < domain.threshold:
                continue
            ranked.append((domain.key, score))
            matched_groups[domain.key] = tuple(sorted(group_weights))

        ranked.sort(key=lambda item: (-item[1], item[0]))
        matched = tuple(key for key, _ in ranked)
        return RoutingDecision(
            scores=dict(ranked),
            matched_domains=matched,
            selected_domains=matched[: self.top_k],
            matched_groups=matched_groups,
            config_version=self.config_version,
        )

    def prompt_modules(self, selected_domains: tuple[str, ...]) -> list[str]:
        bodies = {domain.key: domain.prompt_body for domain in self.domains}
        return [bodies[key] for key in selected_domains if key in bodies]


def _matches(text: str, keyword: DomainKeyword) -> bool:
    term = unicodedata.normalize("NFKC", keyword.term).casefold().strip()
    if not term:
        return False
    if keyword.match_type == "word":
        return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text) is not None
    return term in text
