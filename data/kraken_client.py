"""Cliente async de Kraken con retry, rate limiting y manejo de errores."""
import asyncio
import aiohttp
import hmac
import hashlib
import base64
import urllib.parse
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any

from config import KRAKEN_REST_URL, KRAKEN_API_KEY, KRAKEN_API_SECRET, PAIRS, TIMEFRAMES, TF_MINUTES
from utils.retry import retry
from utils.rate_limiter import rate_limiter
from utils.security import auth_monitor

logger = logging.getLogger(__name__)


class KrakenAPIError(Exception):
    pass


class KrakenClient:
    """Cliente REST async para Kraken."""
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.api_key = KRAKEN_API_KEY
        self.api_secret = KRAKEN_API_SECRET

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()

    def _sign(self, urlpath: str, data: dict) -> str:
        """Firma HMAC-SHA512 para endpoints privados."""
        postdata = urllib.parse.urlencode(data)
        encoded = (str(data["nonce"]) + postdata).encode()
        message = urlpath.encode() + hashlib.sha256(encoded).digest()
        signature = hmac.new(base64.b64decode(self.api_secret), message, hashlib.sha512)
        return base64.b64encode(signature.digest()).decode()

    @retry(max_retries=3, base_delay=1.0, backoff_factor=2.0,
           exceptions=(aiohttp.ClientError, asyncio.TimeoutError, KrakenAPIError))
    async def _request(self, method: str, endpoint: str, params: dict = None,
                       data: dict = None, private: bool = False) -> dict:
        url = f"{KRAKEN_REST_URL}{endpoint}"
        headers = {"User-Agent": "DepaFixBot/1.0"}

        if private:
            if not self.api_key or not self.api_secret:
                raise KrakenAPIError("Credenciales Kraken no configuradas")
            data = data or {}
            data["nonce"] = int(datetime.now().timestamp() * 1000)
            headers["API-Key"] = self.api_key
            headers["API-Sign"] = self._sign(endpoint, data)

        rate_limiter.wait_if_needed("private" if private else "public")

        async with self.session.request(method, url, headers=headers,
                                         params=params, data=data) as resp:
            try:
                result = await resp.json()
            except Exception as e:
                raise KrakenAPIError(f"JSON inválido: {e}")

            if resp.headers:
                rate_limiter.update_from_headers(dict(resp.headers))

            if result.get("error"):
                err_msg = ", ".join(result["error"])
                auth_monitor.handle(err_msg)
                raise KrakenAPIError(f"Kraken error: {err_msg}")

            return result.get("result", {})

    async def fetch_ohlcv(self, pair: str, timeframe: str,
                          since: Optional[int] = None) -> List[Dict[str, Any]]:
        """Obtiene velas OHLCV de Kraken."""
        pair_kraken = pair.replace("/", "")
        params = {
            "pair": pair_kraken,
            "interval": TF_MINUTES.get(timeframe, 60),
        }
        if since:
            params["since"] = since

        data = await self._request("GET", "/0/public/OHLC", params=params)
        raw = data.get(pair_kraken, [])

        candles = []
        for row in raw:
            candles.append({
                "pair": pair,
                "timeframe": timeframe,
                "timestamp": datetime.fromtimestamp(int(row[0])),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "vwap": float(row[5]),
                "volume": float(row[6]),
                "count": int(row[7]),
            })
        return candles

    async def fetch_all_ohlcv(self, since: Optional[int] = None) -> Dict[tuple, List[Dict]]:
        """Consulta todos los pares/timeframes en paralelo."""
        tasks = []
        keys = []
        for pair in PAIRS:
            for tf in TIMEFRAMES:
                tasks.append(self.fetch_ohlcv(pair, tf, since))
                keys.append((pair, tf))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        out = {}
        for key, res in zip(keys, results):
            if isinstance(res, Exception):
                logger.error(f"Error obteniendo {key}: {res}")
                out[key] = []
            else:
                out[key] = res
        return out

    async def get_balance(self) -> dict:
        """Balance de la cuenta (privado)."""
        return await self._request("POST", "/0/private/Balance", private=True)

    async def add_order(self, pair: str, side: str, ordertype: str,
                        volume: float, price: float = None) -> dict:
        """Envía una orden (privado)."""
        data = {
            "pair": pair.replace("/", ""),
            "type": side.lower(),
            "ordertype": ordertype,
            "volume": str(volume),
        }
        if price and ordertype in ("limit", "stop-loss-limit"):
            data["price"] = str(price)
        return await self._request("POST", "/0/private/AddOrder", data=data, private=True)
