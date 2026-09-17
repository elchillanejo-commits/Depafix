"""Buffer de velas con batch insert a Supabase y caché en memoria."""
import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime

from supabase import create_client, Client

from config import SUPABASE_URL, SUPABASE_KEY, BATCH_SIZE, BATCH_FLUSH_INTERVAL

logger = logging.getLogger(__name__)


class VelaBuffer:
    """Acumula velas en memoria y las inserta en batch a Supabase."""
    def __init__(self):
        self._buffer: List[Dict] = []
        self._cache: Dict[tuple, Dict] = {}
        self._lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None
        self._supabase: Optional[Client] = None
        if SUPABASE_URL and SUPABASE_KEY:
            self._supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    async def start(self):
        self._flush_task = asyncio.create_task(self._flush_loop())

    async def stop(self):
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        await self.flush()

    def add(self, candle: Dict):
        key = (candle["pair"], candle["timeframe"])
        cached = self._cache.get(key)
        if cached is None or candle["timestamp"] > cached["timestamp"]:
            self._cache[key] = candle.copy()
        self._buffer.append(candle)

    def get_last(self, pair: str, timeframe: str) -> Optional[Dict]:
        return self._cache.get((pair, timeframe))

    async def flush(self):
        if not self._buffer or not self._supabase:
            return
        async with self._lock:
            to_insert = self._buffer.copy()
            self._buffer.clear()

        rows = []
        for c in to_insert:
            rows.append({
                "pair": c["pair"],
                "timeframe": c["timeframe"],
                "timestamp": c["timestamp"].isoformat() if isinstance(c["timestamp"], datetime) else c["timestamp"],
                "open": c["open"],
                "high": c["high"],
                "low": c["low"],
                "close": c["close"],
                "volume": c["volume"],
            })

        try:
            # Insertar en chunks de BATCH_SIZE
            for i in range(0, len(rows), BATCH_SIZE):
                chunk = rows[i:i + BATCH_SIZE]
                self._supabase.table("ohlcv").upsert(chunk).execute()
            logger.info(f"Insertadas {len(rows)} velas en Supabase")
        except Exception as e:
            logger.error(f"Error batch insert: {e}")
            # Re-encolar para reintento
            async with self._lock:
                self._buffer = rows + self._buffer

    async def _flush_loop(self):
        while True:
            await asyncio.sleep(BATCH_FLUSH_INTERVAL)
            await self.flush()
