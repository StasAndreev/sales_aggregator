import threading
import time

import httpx

CBR_URL = "https://www.cbr-xml-daily.ru/daily_json.js"
_CACHE_TTL = 3600

_cached_rate: float | None = None
_cache_ts: float = 0.0
_lock = threading.Lock()


class CurrencyUnavailableError(Exception):
    pass


def get_usd_rate() -> float:
    """Return RUB per 1 USD from CBR API, cached for 1 hour."""
    global _cached_rate, _cache_ts
    now = time.monotonic()
    if _cached_rate is not None and now - _cache_ts < _CACHE_TTL:
        return _cached_rate
    with _lock:
        now = time.monotonic()
        if _cached_rate is not None and now - _cache_ts < _CACHE_TTL:
            return _cached_rate
        try:
            resp = httpx.get(CBR_URL, timeout=5)
            resp.raise_for_status()
            data = resp.json()
            usd = data["Valute"]["USD"]
            rate = float(usd["Value"]) / float(usd["Nominal"])
        except httpx.HTTPError as exc:
            if _cached_rate is not None:
                return _cached_rate
            raise CurrencyUnavailableError("CBR API not available") from exc
        except (KeyError, ValueError) as exc:
            if _cached_rate is not None:
                return _cached_rate
            raise CurrencyUnavailableError("Unexpected CBR API response format") from exc
        _cached_rate = rate
        _cache_ts = now
        return rate
