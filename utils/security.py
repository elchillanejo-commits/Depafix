"""Capa de seguridad: auth monitor, encriptación, validación de órdenes, IP whitelist, alertas."""
import os
import time
import json
import urllib.request
import urllib.parse
import logging
from typing import Dict, List, Callable, Any

from cryptography.fernet import Fernet

from config import (
    FERNET_MASTER_KEY, ALLOWED_IP,
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    MAX_BALANCE_PCT, MAX_PRICE_DEVIATION, MAX_ORDERS_5MIN,
)

logger = logging.getLogger("TradingBotSecurity")


# ── 1. MONITOR DE AUTENTICACIÓN ──
class KrakenAuthMonitor:
    """Detecta compromiso de API keys y dispara shutdown de emergencia."""
    AUTH_ERRORS = ["EAPI:Invalid key", "EAPI:Invalid signature", "EInvalid nonce", "Permission denied"]

    def __init__(self, failure_threshold: int = 3):
        self.failure_count = 0
        self.failure_threshold = failure_threshold

    def handle(self, error_message: str):
        if any(err in error_message for err in self.AUTH_ERRORS):
            self.failure_count += 1
            logger.error(
                f"⚠️ Auth fallo {self.failure_count}/{self.failure_threshold}: {error_message}"
            )
            if self.failure_count >= self.failure_threshold:
                self._emergency_shutdown()

    def _emergency_shutdown(self):
        logger.critical("🚨 COMPROMISO DE API KEYS DETECTADO. Apagando de emergencia.")
        SecurityNotifier().send("🚨 COMPROMISO DE API KEYS — Bot detenido de emergencia.")
        raise SystemExit("Parada de emergencia por fallo de seguridad.")


# ── 2. ENCRIPTACIÓN DE CREDENCIALES ──
class SecureConfigLoader:
    """Carga .env encriptado con Fernet."""
    def __init__(self, master_key: bytes = FERNET_MASTER_KEY):
        if not master_key:
            raise ValueError("FERNET_MASTER_KEY no configurada")
        self.cipher = Fernet(master_key)

    def encrypt_file(self, plain_path: str, secure_path: str):
        with open(plain_path, "rb") as f:
            data = f.read()
        with open(secure_path, "wb") as f:
            f.write(self.cipher.encrypt(data))
        logger.info(f"Archivo encriptado: {secure_path}")

    def load(self, secure_path: str) -> Dict[str, str]:
        if not os.path.exists(secure_path):
            raise FileNotFoundError(f"No existe {secure_path}")
        with open(secure_path, "rb") as f:
            data = self.cipher.decrypt(f.read())
        env_vars = {}
        for line in data.decode("utf-8").splitlines():
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                env_vars[key.strip()] = val.strip()
        return env_vars


# ── 3. VALIDADOR DE ÓRDENES ──
class OrderValidator:
    """Risk Management Guard: valida órdenes antes de enviar a Kraken."""
    def __init__(self):
        self.order_timestamps: List[float] = []

    def validate(self, order_amount: float, total_balance: float,
                 order_price: float, last_market_price: float) -> bool:
        # 1. Monto máximo
        allowed = total_balance * MAX_BALANCE_PCT
        if order_amount > allowed:
            raise ValueError(f"Monto {order_amount:.2f} excede 5% del balance ({allowed:.2f})")

        # 2. Desviación de precio
        dev = abs(order_price - last_market_price) / last_market_price
        if dev > MAX_PRICE_DEVIATION:
            raise ValueError(f"Desviación {dev:.2%} excede límite {MAX_PRICE_DEVIATION:.0%}")

        # 3. Anti-loop
        now = time.time()
        self.order_timestamps = [t for t in self.order_timestamps if t > now - 300]
        if len(self.order_timestamps) >= MAX_ORDERS_5MIN:
            raise RuntimeError(f"Más de {MAX_ORDERS_5MIN} órdenes en 5 min — posible loop.")

        self.order_timestamps.append(now)
        return True


# ── 4. WHITELIST DE IPs ──
class IPWhitelistValidator:
    def __init__(self, allowed_ip: str = ALLOWED_IP):
        if not allowed_ip:
            logger.warning("ALLOWED_IP no configurada — whitelist desactivada.")
        self.allowed_ip = allowed_ip

    def _get_public_ip(self) -> str:
        try:
            with urllib.request.urlopen("https://api.ipify.org?format=json", timeout=5) as r:
                return json.loads(r.read().decode()).get("ip", "")
        except Exception as e:
            raise ConnectionError(f"No se pudo obtener IP pública: {e}")

    def verify(self):
        if not self.allowed_ip:
            return True
        current = self._get_public_ip()
        if current != self.allowed_ip:
            raise PermissionError(
                f"IP {current} no autorizada (whitelist: {self.allowed_ip})"
            )
        logger.debug(f"IP verificada: {current}")
        return True


# ── 5. NOTIFICADOR DE SEGURIDAD ──
class SecurityNotifier:
    """Alertas a Telegram (y opcionalmente Discord)."""
    def __init__(self):
        self.token = TELEGRAM_BOT_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID
        self.enabled = bool(self.token and self.chat_id)

    def send(self, message: str):
        if not self.enabled:
            logger.warning("Telegram no configurado — alerta omitida.")
            return
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = urllib.parse.urlencode({
            "chat_id": self.chat_id,
            "text": f"🚨 [SECURITY ALERT]\n\n{message}",
            "parse_mode": "Markdown",
        }).encode("utf-8")
        try:
            req = urllib.request.Request(url, data=payload, method="POST")
            with urllib.request.urlopen(req, timeout=5) as r:
                if r.status != 200:
                    logger.error(f"Telegram HTTP {r.status}")
        except Exception as e:
            logger.error(f"Fallo envío Telegram: {e}")


# Instancias globales
auth_monitor = KrakenAuthMonitor()
order_validator = OrderValidator()
ip_validator = IPWhitelistValidator()
notifier = SecurityNotifier()


def secure_kraken_call(func: Callable, *args, **kwargs) -> Any:
    """Wrapper que captura errores de auth y dispara alertas."""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        auth_monitor.handle(str(e))
        raise
