"""Unit tests for SampleQuery serialization and paging defaults."""

from __future__ import annotations

import pytest

from koffer.domain import (
    DEFAULT_PAGE_LIMIT,
    NumericRange,
    PageRequest,
    SampleAvailability,
    SampleFilters,
    SampleQuery,
    SortDirection,
    SortField,
    SortSpec,
)
from koffer.repositories.saved_searches import sample_query_from_json, sample_query_to_json


def test_default_sort_is_name_ascending() -> None:
    query = SampleQuery()
    assert query.sort.field is SortField.NAME
    assert query.sort.direction is SortDirection.ASC
    assert DEFAULT_PAGE_LIMIT == 200


def test_page_request_rejects_invalid_bounds() -> None:
    with pytest.raises(ValueError):
        PageRequest(offset=-1, limit=10)
    with pytest.raises(ValueError):
        PageRequest(offset=0, limit=0)


def test_sample_query_json_roundtrip() -> None:
    query = SampleQuery(
        version=1,
        text="kick",
        filters=SampleFilters(
            sample_type=("One-shot",),
            bpm=NumericRange(min=80, max=140),
            availability=(SampleAvailability.ONLINE,),
            favorite=True,
        ),
        sort=SortSpec(field=SortField.DURATION, direction=SortDirection.DESC),
    )
    restored = sample_query_from_json(sample_query_to_json(query))
    assert restored == query
