from pydantic import BaseModel, Field
from typing import List, Optional

# --- 1. Плоский JSON от ESP32 (строго по твоей структуре) ---
class TelemetryPayload(BaseModel):
    gateway_mac: str
    rack_node_mac: str
    emergency: bool = False
    power_220v: bool
    room_temp: float
    room_humidity: float
    rack_online: bool
    temp_in: float
    temp_out: float
    ping_router: bool
    ping_server: bool
    ping_internet: bool


# --- 2. Схемы синхронизации шлюза ---
class GatewaySyncRequest(BaseModel):
    event: str = "gateway_sync"
    gateway_mac: str
    gateway_ip: str
    gateway_rssi: Optional[int] = 0

class GatewaySyncResponse(BaseModel):
    status: str = "synced"
    interval_s: int
    ping_target_ip: str


# --- 3. Схемы для Веб-дашборда Андрея ---
class ConfigUpdateSchema(BaseModel):
    """Пороги, которые Андрей меняет ползунками на сайте."""
    send_interval_s: Optional[int] = Field(None, ge=2, le=300)
    ping_target_ip: Optional[str] = None
    max_room_temp: Optional[float] = Field(None, description="Порог перегрева комнаты (DHT11)")
    max_temp_in: Optional[float] = Field(None, description="Порог вдува стойки (DS18B20 #1)")
    max_temp_out: Optional[float] = Field(None, description="Порог выдува стойки (DS18B20 #2)")
    max_delta_t: Optional[float] = Field(None, description="Порог опасной разницы ΔT")


class DashboardStatusResponse(BaseModel):
    gateway_online: bool
    last_seen_sec_ago: int
    power_220v: bool
    room_temp: float
    room_humidity: float
    rack_online: bool
    rack_temp_in: float
    rack_temp_out: float
    delta_t: float
    ping_router: bool
    ping_server: bool
    ping_internet: bool
    active_incidents: List[str]
    config: dict