import httpx
from datetime import datetime, timezone
from app.config import settings

class TelegramNotifier:
    """Отправка тревожных уведомлений с защитой от спама."""
    
    def __init__(self):
        self.last_alert_text = ""
        self.last_alert_time = 0.0
        self.cooldown_sec = 120.0  # Не повторять идентичный алерт чаще, чем раз в 2 минуты

    async def send_message(self, text: str):
        if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
            print(f"[Telegram Mock]: {text}")
            return

        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": settings.TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML"
        }
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                await client.post(url, json=payload)
        except Exception as e:
            print(f"[Telegram Error]: Не удалось отправить сообщение: {e}")

    async def notify_incident(self, incidents: list[str], severity: str, is_emergency: bool = False):
        if not incidents:
            return

        now = datetime.now(timezone.utc).timestamp()
        full_text = "\n".join(f"• {inc}" for inc in incidents)
        
        # Защита от спама каждые 10 сек (если ЧП то же самое и кулдаун не истек)
        if not is_emergency and full_text == self.last_alert_text and (now - self.last_alert_time) < self.cooldown_sec:
            return

        self.last_alert_text = full_text
        self.last_alert_time = now

        icon = "🚨" if severity == "CRITICAL" else "⚠️"
        msg = (
            f"<b>{icon} ServerGuard IoT: ТРЕВОГА [{severity}]</b>\n\n"
            f"{full_text}\n\n"
            f"<i>Время: {datetime.now().strftime('%H:%M:%S')} | Требуется внимание</i>"
        )
        await self.send_message(msg)

    async def notify_recovery(self):
        self.last_alert_text = ""
        msg = "<b>✅ ServerGuard IoT: ВСЕ СИСТЕМЫ В НОРМЕ</b>\n\nФизические параметры и сетевые сервисы восстановлены."
        await self.send_message(msg)

notifier = TelegramNotifier()