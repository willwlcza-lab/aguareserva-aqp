"""Traduce las tablas sin borrar datos. También funciona sobre una instalación nueva."""

from alembic import op

revision = "es20261125"
down_revision = "b1090d72bb08"
branch_labels = None
depends_on = None
TABLAS = {
    "users": "usuarios",
    "sessions": "sesiones",
    "rate_limits": "limites_intentos",
    "households": "hogares",
    "containers": "recipientes",
    "movements": "movimientos",
    "plans": "planes",
    "audit_events": "eventos_auditoria",
}


def upgrade():
    for anterior, nuevo in TABLAS.items():
        op.rename_table(anterior, nuevo)


def downgrade():
    for anterior, nuevo in reversed(list(TABLAS.items())):
        op.rename_table(nuevo, anterior)
