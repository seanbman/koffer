"""Typed persistence repositories. Connections are owned by the caller."""

from koffer.repositories.classifications import ClassificationRepository
from koffer.repositories.collections import CollectionMembership, CollectionRepository
from koffer.repositories.exclusions import SourceExclusionRepository
from koffer.repositories.jobs import JobRepository
from koffer.repositories.samples import SampleRepository
from koffer.repositories.saved_searches import SavedSearchRepository
from koffer.repositories.sources import SourceRepository
from koffer.repositories.suggestions import SuggestionRepository
from koffer.repositories.tags import TagRepository
from koffer.repositories.technical_metadata import TechnicalMetadataRepository

__all__ = [
    "ClassificationRepository",
    "CollectionMembership",
    "CollectionRepository",
    "JobRepository",
    "SampleRepository",
    "SavedSearchRepository",
    "SourceExclusionRepository",
    "SourceRepository",
    "SuggestionRepository",
    "TagRepository",
    "TechnicalMetadataRepository",
]
