from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from datetime import datetime, timezone

from app.database import get_db
from app.models import SystemConfig, TelemetryLog, GatewayState
from app.schemas import ConfigUpdateSchema, DashboardStatusResponse

router = APIRouter(prefix="/api", tags=["Frontend Dashboard & Prometheus"])

@router.get("/status", response_model=DashboardStatusResponse)
async def get_dashboard_status(db: AsyncSession = Depends(get_db)):
    """Живой статус для Веб-дашборда Андрея (опрашивается каждые 2–5 сек)."""
    cfg_res = await db.execute(select(SystemConfig).where(SystemConfig.id == 1))
    cfg = cfg_res.scalar_one_or_none() or SystemConfig()

    state_res = await db.execute(select(GatewayState).order_by(GatewayState.last_seen.desc()))
    state = state_res.scalars().first()

    log_res = await db.execute(select(TelemetryLog).order_by(desc(TelemetryLog.timestamp)))
    last_log = log_res.scalars().first()

    last_seen_sec = 9999
    gateway_online = False
    if state and state.last_seen:
        diff = (datetime.now(timezone.utc) - state.last_seen.replace(tzinfo=timezone.utc)).total_seconds()
        last_seen_sec = int(diff)
        gateway_online = (last_seen_sec <= (cfg.send_interval_s * 3))

    active_incidents = state.last_incident.split(" | ") if (state and state.last_incident) else []

    return DashboardStatusResponse(
        gateway_online=gateway_online,
        last_seen_sec_ago=last_seen_sec,
        power_220v=last_log.power_220v if last_log else True,
        room_temp=last_log.room_temp if last_log else 0.0,
        room_humidity=last_log.room_humidity if last_log else 0.0,
        rack_online=(last_log.rack_temp_in > -50) if last_log else False,
        rack_temp_in=last_log.rack_temp_in if last_log else 0.0,
        rack_temp_out=last_log.rack_temp_out if last_log else 0.0,
        delta_t=last_log.delta_t if last_log else 0.0,
        ping_router=last_log.ping_router if last_log else False,
        ping_server=last_log.ping_server if last_log else False,
        ping_internet=last_log.ping_internet if last_log else False,
        active_incidents=active_incidents,
        config={
            "send_interval_s": cfg.send_interval_s,
            "ping_target_ip": cfg.ping_target_ip,
            "max_room_temp": cfg.max_room_temp,
            "max_temp_in": cfg.max_temp_in,
            "max_temp_out": cfg.max_temp_out,
            "max_delta_t": cfg.max_delta_t
        }
    )

@router.get("/history")
async def get_history(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """Данные для построения графиков за сутки/неделю (для Андрея)."""
    res = await db.execute(select(TelemetryLog).order_by(desc(TelemetryLog.timestamp)).limit(limit))
    rows = res.scalars().all()
    return [{
        "time": r.timestamp.strftime("%H:%M:%S"),
        "temp_in": r.rack_temp_in,
        "temp_out": r.rack_temp_out,
        "delta_t": r.delta_t,
        "room_temp": r.room_temp,
        "power_220v": r.power_220v
    } for r in reversed(rows)]

@router.post("/config")
async def update_config(payload: ConfigUpdateSchema, db: AsyncSession = Depends(get_db)):
    """Изменение порогов и правил из интерфейса Андрея."""
    res = await db.execute(select(SystemConfig).where(SystemConfig.id == 1))
    cfg = res.scalar_one_or_none()
    if not cfg:
        cfg = SystemConfig(id=1)
        db.add(cfg)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(cfg, field, value)

    await db.commit()
    return {"status": "updated", "config": payload.model_dump(exclude_unset=True)}

@router.get("/metrics")
async def prometheus_metrics(db: AsyncSession = Depends(get_db)):
    """Специальный экспорт для Prometheus (требование DevOps из опроса)."""
    log_res = await db.execute(select(TelemetryLog).order_by(desc(TelemetryLog.timestamp)))
    l = log_res.scalars().first()
    if not l:
        return Response(content="# No data\n", media_type="text/plain")

    lines = [
        f"serverguard_power_220v {1 if l.power_220v else 0}",
        f"serverguard_room_temperature_celsius {l.room_temp}",
        f"serverguard_room_humidity_percent {l.room_humidity}",
        f"serverguard_rack_temp_intake_celsius {l.rack_temp_in}",
        f"serverguard_rack_temp_exhaust_celsius {l.rack_temp_out}",
        f"serverguard_rack_delta_t_celsius {l.delta_t}",
        f"serverguard_ping_server_up {1 if l.ping_server else 0}",
        f"serverguard_ping_router_up {1 if l.ping_router else 0}"
    ]
    return Response(content="\n".join(lines) + "\n", media_type="text/plain")