from typing import List, Tuple
from app.models import SystemConfig
from app.schemas import TelemetryPayload

class TriageEngine:
    """Дерево решений: сравнивает сырые замеры ESP32 с порогами из БД."""

    @staticmethod
    def analyze(data: TelemetryPayload, cfg: SystemConfig) -> Tuple[List[str], str]:
        incidents = []
        severity = "OK"  # "OK", "WARNING", "CRITICAL"

        # 1. Диагностика электросети 220В
        if not data.power_220v:
            incidents.append("⚡ АВАРИЯ: Отключено питание 220В! Шлюз перешел на резервный Li-Po.")
            severity = "CRITICAL"

        # 2. Диагностика сети («Тройной пинг»)
        if not data.ping_router:
            incidents.append("📡 СБОЙ СЕТИ: Локальный роутер не отвечает на пинг.")
            if severity != "CRITICAL": severity = "WARNING"
        elif not data.ping_server:
            # Роутер жив, но сервер кафедры упал (кейс PWS!)
            incidents.append("🛠 ОТКАЗ СЕРВЕРА: Сервер PWS перестал отвечать! Свет и роутер в норме (аппаратный сбой диска/ОС).")
            severity = "CRITICAL"
        elif not data.ping_internet:
            incidents.append("🌐 ВНЕШНИЙ СБОЙ: Пропал интернет-канал (8.8.8.8). Локальная сеть исправна.")
            if severity != "CRITICAL": severity = "WARNING"

        # 3. Диагностика климата зала (DHT11) по порогу из БД (max_room_temp)
        if data.room_temp > -50.0:
            if data.room_temp >= cfg.max_room_temp:
                incidents.append(f"❄️ СБОЙ ОХЛАЖДЕНИЯ: В комнате {data.room_temp:.1f}°C (порог в БД: {cfg.max_room_temp}°C).")
                if severity != "CRITICAL": severity = "WARNING"

            if data.room_humidity > cfg.max_humidity:
                incidents.append(f"💧 ОПАСНАЯ ВЛАЖНОСТЬ: {data.room_humidity:.1f}% (риск конденсата).")
            elif 0 <= data.room_humidity < cfg.min_humidity:
                incidents.append(f"⚡ СУХОЙ ВОЗДУХ: {data.room_humidity:.1f}% (риск статики).")

        # 4. Диагностика стойки: расчет ΔT и проверка порогов из БД
        if not data.rack_online:
            incidents.append(f"⚠️ ТЕЛЕМЕТРИЯ: Нет радиосвязи с датчиком стойки ({data.rack_node_mac}).")
        else:
            # Сервер сам вычисляет Дельту
            delta_t = (data.temp_out - data.temp_in) if (data.temp_in > -50 and data.temp_out > -50) else 0.0

            # Сверка выдува с порогом max_temp_out
            if data.temp_out >= cfg.max_temp_out:
                incidents.append(f"🔥 ПЕРЕГРЕВ ВЫДУВА: {data.temp_out:.1f}°C (порог в БД: {cfg.max_temp_out}°C)!")
                severity = "CRITICAL"

            # Сверка дельты с порогом max_delta_t
            if delta_t >= cfg.max_delta_t:
                incidents.append(f"🌪 ОТКАЗ ВЕНТИЛЯТОРА: Разница ΔT = +{delta_t:.1f}°C превысила норму ({cfg.max_delta_t}°C)!")
                severity = "CRITICAL"

            # Проверка эффекта духовки
            if data.temp_in >= cfg.max_temp_in and data.room_temp < cfg.max_room_temp:
                incidents.append(f"📦 ЭФФЕКТ ДУХОВКИ: В зале прохладно ({data.room_temp:.1f}°C), а на вдуве стойки застой ({data.temp_in:.1f}°C)!")
                if severity != "CRITICAL": severity = "WARNING"

        return incidents, severity