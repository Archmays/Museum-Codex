from __future__ import annotations

from museum_pipeline.adapters.aic import AicAdapter
from museum_pipeline.adapters.getty_ulan import GettyUlanAdapter
from museum_pipeline.adapters.met import MetOpenAccessAdapter
from museum_pipeline.adapters.wikidata import WikidataAdapter
from museum_pipeline.errors import PipelineError


ADAPTER_TYPES = (WikidataAdapter, GettyUlanAdapter, MetOpenAccessAdapter, AicAdapter)


def adapters_by_source() -> dict[str, object]:
    return {adapter_type.source_id: adapter_type() for adapter_type in ADAPTER_TYPES}


def get_adapter(source_id: str):
    try:
        return adapters_by_source()[source_id]
    except KeyError as error:
        raise PipelineError("adapter_unknown", f"Unknown adapter: {source_id}") from error
