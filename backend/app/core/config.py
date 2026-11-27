from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracion(BaseSettings):
    database_url: str = (
        "postgresql+psycopg://postgres:CAMBIAR@localhost:5432/aguareserva"
    )
    cookie_secure: bool = False  # True exclusivamente cuando el sitio sirve por HTTPS.
    cookie_name: str = "aqp_session"
    session_hours: int = 8
    session_idle_minutes: int = 30
    sedapar_gob_minutos: int = Field(default=60, ge=15, le=10080)
    cortes_complementarios_minutos: int = Field(default=30, ge=15, le=10080)
    cisternas_complementarias_minutos: int = Field(default=30, ge=15, le=10080)
    manos_unidas_minutos: int = Field(default=1440, ge=60, le=10080)
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Configuracion()
