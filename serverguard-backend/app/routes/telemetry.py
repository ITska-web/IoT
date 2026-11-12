from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone

from app.database import get_db
from app.models import SystemConfig, TelemetryLog, GatewayState
from app.schemas import GatewaySyncRequest, GatewaySyncResponse, TelemetryPayload
from app.triage import TriageEngine
from app.telegram_bot import notifier

router = APIRouter(prefix="/api", tags=["Hardware Telemetry"])

@router.post("/sync", response_model=GatewaySyncResponse)
async def sync_gateway(payload: GatewaySyncRequest, db: AsyncSession = Depends(get_db)):
    """Первоначальное рукопожатие шлюза с сервером."""
    res = await db.execute(select(SystemConfig).where(SystemConfig.id == 1))
    cfg = res.scalar_one_or_none()
    if not cfg:
        cfg = SystemConfig(id=1)
        db.add(cfg)
        await db.commit()
        await db.refresh(cfg)

    state_res = await db.execute(select(GatewayState).where(GatewayState.gateway_mac == payload.gateway_mac))
    state = state_res.scalar_one_or_none()
    if not state:
        state = GatewayState(gateway_mac=payload.gateway_mac)
        db.add(state)

    state.gateway_ip = payload.gateway_ip
    state.last_seen = datetime.now(timezone.utc)
    state.is_online = True
    await db.commit()

    return GatewaySyncResponse(
        status="synced",
        interval_s=cfg.send_interval_s,
        ping_target_ip=cfg.ping_target_ip
    )

@router.post("/telemetry")
async def receive_telemetry(payload: TelemetryPayload, db: AsyncSession = Depends(get_db)):
    """Прием регулярных чистых замеров от ESP32."""
    # 1. Достаем актуальные пороги из БД
    res = await db.execute(select(SystemConfig).where(SystemConfig.id == 1))
    cfg = res.scalar_one_or_none() or SystemConfig()

    # 2. Обновляем статус жизни шлюза
    state_res = await db.execute(select(GatewayState).where(GatewayState.gateway_mac == payload.gateway_mac))
    state = state_res.scalar_one_or_none()
    if not state:
        state = GatewayState(gateway_mac=payload.gateway_mac)
        db.add(state)

    state.last_seen = datetime.now(timezone.utc)
    state.is_online = True

    # 3. Запускаем сравнение замеров с порогами
    incidents, severity = TriageEngine.analyze(payload, cfg)
    state.last_incident = " | ".join(incidents) if incidents else None

    # 4. Если выявлено ЧП — отправляем алерт в Telegram
    if incidents:
        await notifier.notify_incident(incidents, severity, is_emergency=payload.emergency)

    # 5. Считаем дельту и сохраняем замер в таблицу логов
    delta_t = (payload.temp_out - payload.temp_in) if (payload.temp_in > -50 and payload.temp_out > -50) else 0.0

    log_entry = TelemetryLog(
        power_220v=payload.power_220v,
        room_temp=payload.room_temp,
        room_humidity=payload.room_humidity,
        rack_temp_in=payload.temp_in,
        rack_temp_out=payload.temp_out,
        delta_t=delta_t,
        ping_router=payload.ping_router,
        ping_server=payload.ping_server,
        ping_internet=payload.ping_internet
    )
    db.add(log_entry)
    await db.commit()

    # 6. Отвечаем плате: отдаем текущий интервал опроса из БД
    return {
        "status": "ok",
        "severity": severity,
        "interval_s": cfg.send_interval_s
    }