from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime
from datetime import datetime, timezone
from app.database import Base

class SystemConfig(Base):
    """Единый источник истины (Single Source of Truth) для порогов и правил."""
    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True, default=1)
    send_interval_s = Column(Integer, default=10)
    ping_target_ip = Column(String, default="192.168.1.50")    # Сервер PWS
    ping_internet_ip = Column(String, default="8.8.8.8")
    
    # Пороги температур (живут ТОЛЬКО здесь, не на ESP32!)
    max_room_temp = Column(Float, default=28.0)
    max_temp_in = Column(Float, default=27.0)
    max_temp_out = Column(Float, default=45.0)
    max_delta_t = Column(Float, default=15.0)
    min_humidity = Column(Float, default=20.0)
    max_humidity = Column(Float, default=80.0)


class TelemetryLog(Base):
    """История телеметрии для графиков Андрея."""
    __tablename__ = "telemetry_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    power_220v = Column(Boolean, nullable=False)
    room_temp = Column(Float)
    room_humidity = Column(Float)
    rack_temp_in = Column(Float)
    rack_temp_out = Column(Float)
    delta_t = Column(Float)
    ping_router = Column(Boolean)
    ping_server = Column(Boolean)
    ping_internet = Column(Boolean)


class GatewayState(Base):
    """Текущее живое состояние шлюза (для Heartbeat и дашборда)."""
    __tablename__ = "gateway_state"

    gateway_mac = Column(String, primary_key=True)
    gateway_ip = Column(String)
    last_seen = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_online = Column(Boolean, default=True)
    last_incident = Column(String, nullable=True)