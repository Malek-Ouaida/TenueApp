from pydantic import BaseModel


class ClosetMetadataCategoryOption(BaseModel):
    name: str
    subcategories: list[str]


class ClosetMetadataOptionsResponse(BaseModel):
    taxonomy_version: str
    required_confirmation_fields: list[str]
    lifecycle_statuses: list[str]
    processing_statuses: list[str]
    review_statuses: list[str]
    categories: list[ClosetMetadataCategoryOption]
    colors: list[str]
    materials: list[str]
    patterns: list[str]
    style_tags: list[str]
    occasion_tags: list[str]
    season_tags: list[str]
