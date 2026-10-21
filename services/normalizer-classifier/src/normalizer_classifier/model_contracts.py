from __future__ import annotations

from typing import Protocol

import httpx

from .models import AIModelCallUsage, AuxiliaryModelResponse, ModelResponse, NormalizedItem, RawItem, SourceMetadata
from .taxonomy import TaxonomyContext


class ModelClientError(RuntimeError):
    def __init__(self, message: str, *, usage: AIModelCallUsage | None = None, retryable: bool = True) -> None:
        super().__init__(message)
        self.usage = usage
        self.retryable = retryable


class ModelClient(Protocol):
    provider: str
    api_provider: str
    model: str

    async def classify(
        self, raw_item: RawItem, source: SourceMetadata, normalized: NormalizedItem,
        *, taxonomy_context: TaxonomyContext | None = None,
        domain_modules: list[str] | None = None, enabled_domain_keys: list[str] | None = None,
    ) -> ModelResponse: ...

    async def summarize_and_translate(
        self, raw_item: RawItem, source: SourceMetadata, normalized: NormalizedItem,
        *, full_translation_required: bool = True, input_text: str | None = None,
        truncated: bool = False, taxonomy_context: TaxonomyContext | None = None,
    ) -> AuxiliaryModelResponse: ...


def is_retryable_model_error(error: Exception) -> bool:
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
        return status in {408, 429} or 500 <= status < 600
    return isinstance(error, (httpx.TransportError, ValueError, KeyError, IndexError, TypeError, AttributeError))
