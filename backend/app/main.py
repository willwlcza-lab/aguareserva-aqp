from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy import text
from .core.db import SessionLocal
from .routers import auth, water, public, admin, fuentes

app = FastAPI(
    title="AguaReserva AQP",
    version="1.0.0",
    description="Reservas familiares, avisos publicados y abastecimiento con trazabilidad.",
)
for router in (auth.router, water.router, public.router, admin.router, fuentes.router):
    app.include_router(router, prefix="/api/v1")


@app.middleware("http")
async def cabeceras_seguras(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(RequestValidationError)
async def error_validacion(request, exc):
    # No devolvemos input: podría contener una contraseña.
    errors = [
        {"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]}
        for e in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={"detail": "Revisa los campos del formulario.", "errors": errors},
    )


@app.get("/api/v1/health", tags=["Estado"])
def estado_servicio():
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "postgresql", "version": "1.0.0"}
