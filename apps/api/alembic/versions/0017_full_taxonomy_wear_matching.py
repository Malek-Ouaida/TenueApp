from __future__ import annotations

"""full taxonomy wear matching

Revision ID: 0017_full_taxonomy_wear_matching
Revises: 0016_phase_06_lookbook_single_feed
Create Date: 2026-04-11 14:30:00.000000
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa

from alembic import op
from app.domains.closet.models import ApplicabilityState
from app.domains.closet.normalization import normalize_field_value
from app.domains.closet.taxonomy import TAXONOMY_VERSION

# revision identifiers, used by Alembic.
revision: str = "0017_full_taxonomy_wear_matching"
down_revision: str | None = "0016_phase_06_lookbook_single_feed"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


field_states_table = sa.table(
    "closet_item_field_states",
    sa.column("id", sa.Uuid()),
    sa.column("closet_item_id", sa.Uuid()),
    sa.column("field_name", sa.String()),
    sa.column("canonical_value", sa.JSON()),
    sa.column("source", sa.String()),
    sa.column("confidence", sa.Float()),
    sa.column("review_state", sa.String()),
    sa.column("applicability_state", sa.String()),
    sa.column("taxonomy_version", sa.String()),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)

projection_table = sa.table(
    "closet_item_metadata_projection",
    sa.column("id", sa.Uuid()),
    sa.column("taxonomy_version", sa.String()),
    sa.column("category", sa.String()),
    sa.column("subcategory", sa.String()),
    sa.column("primary_color", sa.String()),
    sa.column("secondary_colors", sa.JSON()),
    sa.column("material", sa.String()),
    sa.column("pattern", sa.String()),
    sa.column("style_tags", sa.JSON()),
    sa.column("fit_tags", sa.JSON()),
    sa.column("occasion_tags", sa.JSON()),
    sa.column("season_tags", sa.JSON()),
    sa.column("silhouette", sa.String()),
    sa.column("attributes", sa.JSON()),
)


def upgrade() -> None:
    with op.batch_alter_table("closet_item_metadata_projection") as batch_op:
        batch_op.add_column(sa.Column("formality", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("warmth", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("coverage", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("statement_level", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("versatility", sa.String(length=64), nullable=True))

    with op.batch_alter_table("wear_event_detected_items") as batch_op:
        batch_op.add_column(sa.Column("normalized_metadata_json", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("field_confidences_json", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("matching_explanation_json", sa.JSON(), nullable=True))

    conn = op.get_bind()
    _canonicalize_projection_rows(conn)
    _canonicalize_field_states(conn)


def downgrade() -> None:
    with op.batch_alter_table("wear_event_detected_items") as batch_op:
        batch_op.drop_column("matching_explanation_json")
        batch_op.drop_column("field_confidences_json")
        batch_op.drop_column("normalized_metadata_json")

    with op.batch_alter_table("closet_item_metadata_projection") as batch_op:
        batch_op.drop_column("versatility")
        batch_op.drop_column("statement_level")
        batch_op.drop_column("coverage")
        batch_op.drop_column("warmth")
        batch_op.drop_column("formality")


def _canonicalize_projection_rows(conn: sa.Connection) -> None:
    rows = conn.execute(
        sa.select(
            projection_table.c.id,
            projection_table.c.category,
            projection_table.c.subcategory,
            projection_table.c.primary_color,
            projection_table.c.secondary_colors,
            projection_table.c.material,
            projection_table.c.pattern,
            projection_table.c.style_tags,
            projection_table.c.fit_tags,
            projection_table.c.occasion_tags,
            projection_table.c.season_tags,
            projection_table.c.silhouette,
            projection_table.c.attributes,
        )
    ).mappings()

    for row in rows:
        updates = {
            "taxonomy_version": TAXONOMY_VERSION,
            "category": _normalize_existing_value("category", row["category"]),
            "subcategory": _normalize_existing_value("subcategory", row["subcategory"]),
            "primary_color": _normalize_existing_value("primary_color", row["primary_color"]),
            "secondary_colors": _normalize_existing_value("secondary_colors", row["secondary_colors"]),
            "material": _normalize_existing_value("material", row["material"]),
            "pattern": _normalize_existing_value("pattern", row["pattern"]),
            "style_tags": _normalize_existing_value("style_tags", row["style_tags"]),
            "fit_tags": _normalize_existing_value("fit_tags", row["fit_tags"]),
            "occasion_tags": _normalize_existing_value("occasion_tags", row["occasion_tags"]),
            "season_tags": _normalize_existing_value("season_tags", row["season_tags"]),
            "silhouette": _normalize_existing_value("silhouette", row["silhouette"]),
            "attributes": _normalize_existing_value("attributes", row["attributes"]),
        }
        conn.execute(
            projection_table.update()
            .where(projection_table.c.id == row["id"])
            .values(**updates)
        )


def _canonicalize_field_states(conn: sa.Connection) -> None:
    rows = list(
        conn.execute(
            sa.select(
                field_states_table.c.id,
                field_states_table.c.closet_item_id,
                field_states_table.c.field_name,
                field_states_table.c.canonical_value,
                field_states_table.c.source,
                field_states_table.c.confidence,
                field_states_table.c.review_state,
                field_states_table.c.applicability_state,
                field_states_table.c.created_at,
                field_states_table.c.updated_at,
            )
        ).mappings()
    )

    rows_by_item: dict[object, dict[str, sa.RowMapping]] = {}
    for row in rows:
        rows_by_item.setdefault(row["closet_item_id"], {})[str(row["field_name"])] = row

    for row in rows:
        field_name = str(row["field_name"])
        if field_name not in {
            "category",
            "subcategory",
            "primary_color",
            "secondary_colors",
            "colors",
            "material",
            "pattern",
            "style_tags",
            "fit_tags",
            "occasion_tags",
            "season_tags",
            "silhouette",
            "attributes",
            "formality",
            "warmth",
            "coverage",
            "statement_level",
            "versatility",
        }:
            continue

        canonical_value = _normalize_existing_value(
            field_name,
            row["canonical_value"],
            applicability_state=_parse_applicability_state(row["applicability_state"]),
        )
        conn.execute(
            field_states_table.update()
            .where(field_states_table.c.id == row["id"])
            .values(
                canonical_value=canonical_value,
                taxonomy_version=TAXONOMY_VERSION,
            )
        )

    for closet_item_id, by_name in rows_by_item.items():
        colors_row = by_name.get("colors")
        if colors_row is None:
            continue

        applicability_state = _parse_applicability_state(colors_row["applicability_state"])
        normalized_colors = _normalize_existing_value(
            "colors",
            colors_row["canonical_value"],
            applicability_state=applicability_state,
        )
        primary_color = None
        secondary_colors = None
        if applicability_state == ApplicabilityState.VALUE and isinstance(normalized_colors, list):
            primary_color = normalized_colors[0] if normalized_colors else None
            secondary_colors = normalized_colors[1:] or None

        if "primary_color" not in by_name:
            conn.execute(
                field_states_table.insert().values(
                    id=uuid4(),
                    closet_item_id=closet_item_id,
                    field_name="primary_color",
                    canonical_value=primary_color,
                    source=colors_row["source"],
                    confidence=colors_row["confidence"],
                    review_state=colors_row["review_state"],
                    applicability_state=colors_row["applicability_state"],
                    taxonomy_version=TAXONOMY_VERSION,
                    created_at=colors_row["created_at"],
                    updated_at=colors_row["updated_at"],
                )
            )

        if "secondary_colors" not in by_name:
            conn.execute(
                field_states_table.insert().values(
                    id=uuid4(),
                    closet_item_id=closet_item_id,
                    field_name="secondary_colors",
                    canonical_value=secondary_colors,
                    source=colors_row["source"],
                    confidence=colors_row["confidence"],
                    review_state=colors_row["review_state"],
                    applicability_state=colors_row["applicability_state"],
                    taxonomy_version=TAXONOMY_VERSION,
                    created_at=colors_row["created_at"],
                    updated_at=colors_row["updated_at"],
                )
            )


def _parse_applicability_state(value: object) -> ApplicabilityState:
    normalized = str(value or "").strip().lower()
    if normalized == ApplicabilityState.VALUE.value:
        return ApplicabilityState.VALUE
    if normalized == ApplicabilityState.NOT_APPLICABLE.value:
        return ApplicabilityState.NOT_APPLICABLE
    return ApplicabilityState.UNKNOWN


def _normalize_existing_value(
    field_name: str,
    raw_value: object,
    *,
    applicability_state: ApplicabilityState | None = None,
) -> object:
    resolved_applicability = applicability_state
    if resolved_applicability is None:
        resolved_applicability = (
            ApplicabilityState.VALUE if _has_value(raw_value) else ApplicabilityState.UNKNOWN
        )

    normalized = normalize_field_value(
        field_name=field_name,
        raw_value=raw_value,
        applicability_state=resolved_applicability,
        confidence=None,
    )
    if normalized.applicability_state != ApplicabilityState.VALUE:
        return None
    return normalized.canonical_value


def _has_value(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return bool(value)
    return True
