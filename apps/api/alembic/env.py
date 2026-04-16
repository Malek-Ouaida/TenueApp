from logging.config import fileConfig

from sqlalchemy import engine_from_config, inspect, pool, text

from alembic import context
from app.core.config import settings
from app.db.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.print_stdout(
    "Resolved database target: "
    f"{settings.database_target} (source: {settings.database_source}, "
    f"host: {settings.database_host or 'unknown'})"
)

# Escape % so SQLAlchemy URLs with special chars do not break config interpolation.
config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = config.get_main_option("sqlalchemy.url")

    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    # Run the version-column widening in its own clean transaction.
    with connectable.begin() as pre_connection:
        widen_alembic_version_num_if_needed(pre_connection)

    # Give Alembic a fresh connection that it fully controls.
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


def widen_alembic_version_num_if_needed(connection) -> None:
    if connection.dialect.name != "postgresql":
        return

    inspector = inspect(connection)
    if "alembic_version" not in inspector.get_table_names():
        return

    version_column = next(
        (
            column
            for column in inspector.get_columns("alembic_version")
            if column["name"] == "version_num"
        ),
        None,
    )
    if version_column is None:
        return

    length = getattr(version_column["type"], "length", None)
    if length is None or length >= 64:
        return

    connection.execute(
        text("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64)")
    )


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()