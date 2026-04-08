import logging
import threading
import time

import httpx

logger = logging.getLogger(__name__)

CBR_URL = "https://www.cbr-xml-daily.ru/daily_json.js"
_CACHE_TTL = 3600

_cached_rate: float | None = None
_cache_ts: float = 0.0
_lock = threading.Lock()


class CurrencyUnavailableError(Exception):
    pass


def get_usd_rate() -> float:
    global _cached_rate, _cache_ts
    now = time.monotonic()
    if _cached_rate is not None and now - _cache_ts < _CACHE_TTL:
        logger.debug("USD rate cache hit: %.4f (age %.0fs)", _cached_rate, now - _cache_ts)
        return _cached_rate
    with _lock:
        now = time.monotonic()
        if _cached_rate is not None and now - _cache_ts < _CACHE_TTL:
            logger.debug("USD rate cache hit: %.4f (age %.0fs)", _cached_rate, now - _cache_ts)
            return _cached_rate
        try:
            logger.info("Fetching USD rate from CBR API")
            resp = httpx.get(CBR_URL, timeout=5)
            resp.raise_for_status()
            data = resp.json()
            usd = data["Valute"]["USD"]
            rate = float(usd["Value"]) / float(usd["Nominal"])
        except httpx.HTTPError as exc:
            if _cached_rate is not None:
                logger.warning("CBR API request failed, using stale cache (rate=%.4f): %s", _cached_rate, exc)
                return _cached_rate
            logger.error("CBR API unavailable, no cached rate: %s", exc)
            raise CurrencyUnavailableError("CBR API not available") from exc
        except (KeyError, ValueError) as exc:
            if _cached_rate is not None:
                logger.warning("Unexpected CBR response, using stale cache (rate=%.4f): %s", _cached_rate, exc)
                return _cached_rate
            logger.error("Unexpected CBR response, no cached rate: %s", exc)
            raise CurrencyUnavailableError("Unexpected CBR API response format") from exc
        logger.info("USD rate fetched: %.4f", rate)
        _cached_rate = rate
        _cache_ts = now
        return rate
