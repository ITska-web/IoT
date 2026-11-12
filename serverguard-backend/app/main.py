import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.config import settings
from app.database import init_db, AsyncSessionLocal
from app.models import GatewayState, SystemConfig
from app.telegram_bot import notifier
from app.routes import telemetry, dashboard

async def heartbeat_worker():
    """Фоновый сторож: проверяет связь со шлюзом каждые 5 секунд."""
    while True:
        await asyncio.sleep(5)
        try:
            async with AsyncSessionLocal() as session:
                cfg_res = await session.execute(select(SystemConfig).where(SystemConfig.id == 1))
                cfg = cfg_res.scalar_one_or_none()
                timeout = (cfg.send_interval_s * 3) if cfg else 30

                state_res = await session.execute(select(GatewayState))
                gateways = state_res.scalars().all()

                for gw in gateways:
                    if gw.last_seen:
                        diff = (datetime.now(timezone.utc) - gw.last_seen.replace(tzinfo=timezone.utc)).total_seconds()
                        if diff > timeout and gw.is_online:
                            gw.is_online = False
                            await session.commit()
                            await notifier.notify_incident(
                                [f"🚨 ПОТЕРЯ СВЯЗИ: Шлюз {gw.gateway_mac} не отвечает более {int(diff)} сек! Возможен блэкаут или зависание роутера."],
                                severity="CRITICAL",
                                is_emergency=True
                            )
        except Exception as e:
            print(f"[Heartbeat Error]: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Старт приложения
    await init_db()
    heartbeat_task = asyncio.create_task(heartbeat_worker())
    print("🚀 ServerGuard Backend запущен и готов к приему данных!")
    yield
    # Остановка приложения
    heartbeat_task.cancel()

app = FastAPI(
    title="ServerGuard IoT Backend API",
    version="1.0.0",
    description="Backend-сервер для независимого мониторинга серверных СибГУТИ",
    lifespan=lifespan
)

# Разрешаем запросы от фронтенда Андрея (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(telemetry.router)
app.include_router(dashboard.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)