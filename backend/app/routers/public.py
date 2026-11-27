from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from ..core.db import obtener_bd
from ..models import Hogar, Recipiente, Plan
from ..catalogs import AREQUIPA_DISTRICTS

router = APIRouter(tags=["Público"])


@router.get("/publico/estadisticas")
def estadisticas_publicas(db=Depends(obtener_bd)):
    count = db.scalar(select(func.count()).select_from(Hogar))
    # No se publican nombres, direcciones, saldos ni grupos pequeños.
    if count < 5:
        return {
            "households": count,
            "districts": None,
            "capacity": None,
            "with_plan": None,
            "privacy_threshold": 5,
        }
    return {
        "households": count,
        "districts": db.scalar(select(func.count(func.distinct(Hogar.district)))),
        "capacity": float(
            db.scalar(
                select(func.coalesce(func.sum(Recipiente.capacity), 0)).where(
                    Recipiente.active.is_(True)
                )
            )
        ),
        "with_plan": db.scalar(select(func.count(func.distinct(Plan.household_id)))),
        "privacy_threshold": 5,
    }


@router.get("/catalogos/distritos")
def distritos():
    return list(AREQUIPA_DISTRICTS)
