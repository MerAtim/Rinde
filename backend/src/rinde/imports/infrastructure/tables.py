"""Tablas de lotes de importación (SQLAlchemy Core), ADR-0023.

El archivo no se guarda: solo su nombre, su huella SHA-256 y lo que se leyó.
"""

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    String,
    Table,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from rinde.shared.infrastructure.database import metadata

import_batches = Table(
    "import_batches",
    metadata,
    Column("id", Uuid, primary_key=True),
    # El borrado de un usuario borra sus lotes: es el borrado completo de sus datos.
    Column("owner_id", Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("account_id", Uuid, nullable=False),
    Column("currency", String(3), nullable=False),
    Column("file_name", String(255), nullable=False),
    Column("file_sha256", String(64), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("confirmed_at", DateTime(timezone=True), nullable=True),
    Column("imported", Integer, nullable=False),
    Column("skipped", Integer, nullable=False),
    # Las líneas que no se pudieron leer: [{"line": 4, "problem": "LINE_DATE_INVALID"}].
    Column("errors", JSONB, nullable=False),
    # La cuenta es de la misma persona y está en la moneda del lote.
    ForeignKeyConstraint(
        ["account_id", "owner_id", "currency"],
        ["accounts.id", "accounts.owner_id", "accounts.currency"],
        name="account_of_the_same_owner_and_currency",
    ),
    CheckConstraint("char_length(btrim(file_name)) BETWEEN 1 AND 255", name="file_name_length"),
    CheckConstraint("file_sha256 ~ '^[0-9a-f]{64}$'", name="file_sha256_is_sha256"),
    CheckConstraint("imported >= 0 AND skipped >= 0", name="counts_not_negative"),
    CheckConstraint(
        "confirmed_at IS NOT NULL OR (imported = 0 AND skipped = 0)",
        name="counts_only_when_confirmed",
    ),
    CheckConstraint(
        "confirmed_at IS NULL OR confirmed_at >= created_at", name="confirmed_after_created"
    ),
    # La limpieza busca los vencidos sin confirmar.
    Index(
        "ix_import_batches_created_at_pending",
        "created_at",
        postgresql_where=text("confirmed_at IS NULL"),
    ),
)

import_lines = Table(
    "import_lines",
    metadata,
    Column("batch_id", Uuid, ForeignKey("import_batches.id", ondelete="CASCADE"), nullable=False),
    Column("number", Integer, nullable=False),
    Column("occurred_on", Date, nullable=False),
    Column("description", String(120), nullable=True),
    # Con signo: negativo es gasto. La escala de movimientos, que admite Bitcoin.
    Column("amount", Numeric(20, 8), nullable=False),
    Column("fingerprint", String(64), nullable=False),
    Column("status", String(20), nullable=False),
    PrimaryKeyConstraint("batch_id", "number"),
    CheckConstraint("number >= 1", name="number_positive"),
    CheckConstraint("amount <> 0", name="amount_not_zero"),
    CheckConstraint("fingerprint ~ '^[0-9a-f]{64}$'", name="fingerprint_is_sha256"),
    CheckConstraint("status IN ('new', 'duplicate', 'possible_duplicate')", name="status_known"),
)
