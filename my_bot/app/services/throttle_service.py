from datetime import datetime
from sqlalchemy import select, insert, update, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased
from app.models.rate_limit import InboundMessage, RateLimit
from sqlalchemy.dialects.postgresql import insert as pg_insert


def floor_to_minute(ts: datetime) -> datetime:
    # asume tz-aware; si no, usa utcnow()
    return ts.replace(second=0, microsecond=0)

def claim_message_idempotent(db: Session, message_sid: str, from_number: str, body: str | None) -> bool:
    """
    Intenta registrar el SID. Si ya existe, devuelve False (duplicado).
    """
    if not message_sid:
        return True  # sin SID, no podemos asegurar; permitimos seguir
    try:
        db.execute(
            insert(InboundMessage).values(
                message_sid=message_sid, from_number=from_number, body=body
            )
        )
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        return False

def check_rate_limit(db: Session, from_number: str, limit_per_minute: int = 60) -> bool:
    """
    Suma 1 al contador del (número, minuto). Si no existe la fila, la crea con count=1.
    Devuelve True si aún está dentro del límite; False si lo excedió.
    """
    now = func.now()
    win = func.date_trunc("minute", now)

    stmt = (
        pg_insert(RateLimit)
        .values(from_number=from_number, window_start=win, count=1)
        .on_conflict_do_update(
            index_elements=["from_number", "window_start"],
            set_={"count": RateLimit.count + 1, "updated_at": func.now()},
        )
        .returning(RateLimit.count)
    )

    current = db.execute(stmt).scalar_one()
    db.commit()
    return current <= limit_per_minute

def cleanup_old_rows(db: Session, keep_hours: int = 24):
    """
    Limpia filas viejas para mantener tablas chicas (opcional; llama 1 vez al día).
    """
    db.execute(
        f"DELETE FROM rate_limits WHERE window_start < now() - interval '{keep_hours} hours'"
    )
    db.execute(
        f"DELETE FROM inbound_messages WHERE received_at < now() - interval '{keep_hours} hours'"
    )
    db.commit()
