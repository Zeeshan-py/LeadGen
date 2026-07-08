"""Source mapping utilities for external lead data providers."""

from __future__ import annotations

from typing import Any

from .models import merge_unique

SourceMap = dict[str, list[str]]
SocialSourceMap = dict[str, dict[str, list[str]]]


def add_source(target: SourceMap, key: str, source: str) -> None:
    if not key or not source:
        return
    target[key] = merge_unique(target.get(key, []), [source])


def normalize_source_map(raw: Any) -> SourceMap:
    if not isinstance(raw, dict):
        return {}
    result: SourceMap = {}
    for key, values in raw.items():
        key_text = str(key).strip() if key is not None else ""
        normalized_values = values if isinstance(values, list) else [values]
        for value in normalized_values:
            source_text = str(value).strip() if value is not None else ""
            add_source(result, key_text, source_text)
    return result


def normalize_social_source_map(raw: Any) -> SocialSourceMap:
    if not isinstance(raw, dict):
        return {}
    result: SocialSourceMap = {}
    for network, links in raw.items():
        if not isinstance(links, dict):
            continue
        network_text = str(network).strip() if network is not None else ""
        if not network_text:
            continue
        for link, sources in links.items():
            link_text = str(link).strip() if link is not None else ""
            if not link_text:
                continue
            normalized_sources = sources if isinstance(sources, list) else [sources]
            bucket = result.setdefault(network_text, {}).setdefault(link_text, [])
            bucket.extend(
                source
                for source in (
                    str(value).strip() if value is not None else ""
                    for value in normalized_sources
                )
                if source and source not in bucket
            )
    return result


def merge_source_map(target: SourceMap, source: Any) -> None:
    for key, values in normalize_source_map(source).items():
        target[key] = merge_unique(target.get(key, []), values)


def merge_social_source_map(target: SocialSourceMap, source: Any) -> None:
    for network, links in normalize_social_source_map(source).items():
        network_bucket = target.setdefault(network, {})
        for link, values in links.items():
            network_bucket[link] = merge_unique(network_bucket.get(link, []), values)


def merged_source_maps(left: Any, right: Any) -> SourceMap:
    merged = normalize_source_map(left)
    merge_source_map(merged, right)
    return merged


def merged_social_source_maps(left: Any, right: Any) -> SocialSourceMap:
    merged = normalize_social_source_map(left)
    merge_social_source_map(merged, right)
    return merged
