from __future__ import annotations

import re
from dataclasses import dataclass, field


TAG_SEPARATOR_RE = re.compile(r"[\s_/.]+")
TAG_CLEAN_RE = re.compile(r"[^a-z0-9-]+")
TAG_DASH_RE = re.compile(r"-{2,}")
ACTOR_SPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class CategoryOption:
    key: str
    label_en: str
    description: str | None = None


@dataclass(frozen=True)
class TagOption:
    key: str
    label: str
    tag_type: str = "topic"
    aliases: tuple[str, ...] = ()


@dataclass
class TaxonomyContext:
    categories: list[CategoryOption] = field(default_factory=list)
    tags: list[TagOption] = field(default_factory=list)

    @property
    def category_keys(self) -> set[str]:
        return {category.key for category in self.categories}

    @property
    def tag_aliases(self) -> dict[str, str]:
        aliases: dict[str, str] = {}
        for tag in self.tags:
            aliases[normalize_tag_key(tag.key)] = tag.key
            for alias in tag.aliases:
                normalized = normalize_tag_key(alias)
                if normalized:
                    aliases[normalized] = tag.key
        return aliases


def normalize_category(value: str | None, context: TaxonomyContext) -> str:
    key = normalize_tag_key(value or "")
    if key in context.category_keys:
        return key
    return "other"


def normalize_tag_key(value: str) -> str:
    key = value.strip().lower()
    key = TAG_SEPARATOR_RE.sub("-", key)
    key = TAG_CLEAN_RE.sub("", key)
    key = TAG_DASH_RE.sub("-", key).strip("-")
    return key[:80]


def normalize_topic_tags(values: list[str], context: TaxonomyContext, *, limit: int = 12) -> list[str]:
    aliases = context.tag_aliases
    normalized: list[str] = []
    for value in values:
        key = normalize_tag_key(value)
        if not key:
            continue
        key = aliases.get(key, key)
        if key not in normalized:
            normalized.append(key)
        if len(normalized) >= limit:
            break
    return normalized


def normalize_actors(values: list[str], *, limit: int = 12) -> list[str]:
    normalized: list[str] = []
    for value in values:
        actor = ACTOR_SPACE_RE.sub(" ", str(value).strip())
        actor = actor.strip(" \t\r\n,.;:|")
        if not actor:
            continue
        actor = actor[:120]
        if actor not in normalized:
            normalized.append(actor)
        if len(normalized) >= limit:
            break
    return normalized
