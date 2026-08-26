"""Rate-limited free-source adapters; none are permitted to fabricate data."""
from datetime import datetime, timezone
import threading
import time
from typing import Mapping

import requests


class CachedJsonSource:
    def __init__(self, timeout=8, min_interval_sec=0.25):
        self.timeout = float(timeout)
        self.min_interval_sec = float(min_interval_sec)
        self._last_request = 0.0
        self._cache = {}
        self._lock = threading.Lock()

    def _get(self, url, params=None, headers=None, ttl=300):
        key = (url, tuple(sorted((params or {}).items())))
        now = time.monotonic()
        cached = self._cache.get(key)
        if cached and now - cached[0] < ttl:
            return cached[1], cached[2]
        with self._lock:
            wait = self.min_interval_sec - (time.monotonic() - self._last_request)
            if wait > 0:
                time.sleep(wait)
            response = requests.get(url, params=params, headers=headers, timeout=self.timeout)
            self._last_request = time.monotonic()
        response.raise_for_status()
        payload = response.json()
        observed_at = datetime.now(timezone.utc).isoformat()
        self._cache[key] = (time.monotonic(), payload, observed_at)
        return payload, observed_at


class SecEdgarSource(CachedJsonSource):
    BASE = "https://data.sec.gov"

    def __init__(self, user_agent, **kwargs):
        super().__init__(min_interval_sec=max(0.11, kwargs.pop("min_interval_sec", 0.11)), **kwargs)
        self.user_agent = str(user_agent or "").strip()
        if "@" not in self.user_agent:
            raise ValueError("SEC User-Agent must identify an application and contact email")

    def submissions(self, cik, ttl=300):
        cik = str(cik).strip().zfill(10)
        payload, observed = self._get(
            f"{self.BASE}/submissions/CIK{cik}.json",
            headers={"User-Agent": self.user_agent, "Accept-Encoding": "gzip, deflate"},
            ttl=ttl,
        )
        return {"source": "SEC_EDGAR", "observed_at": observed, "payload": payload}

    def company_facts(self, cik, ttl=3600):
        cik = str(cik).strip().zfill(10)
        payload, observed = self._get(
            f"{self.BASE}/api/xbrl/companyfacts/CIK{cik}.json",
            headers={"User-Agent": self.user_agent, "Accept-Encoding": "gzip, deflate"},
            ttl=ttl,
        )
        return {"source": "SEC_XBRL", "observed_at": observed, "payload": payload}


class FredVintageSource(CachedJsonSource):
    BASE = "https://api.stlouisfed.org/fred"

    def __init__(self, api_key, **kwargs):
        super().__init__(**kwargs)
        self.api_key = str(api_key or "").strip()
        if not self.api_key:
            raise ValueError("FRED API key required")

    def observations(self, series_id, realtime_start, realtime_end, ttl=3600):
        payload, observed = self._get(
            f"{self.BASE}/series/observations",
            params={
                "api_key": self.api_key,
                "file_type": "json",
                "series_id": str(series_id),
                "realtime_start": str(realtime_start),
                "realtime_end": str(realtime_end),
            },
            ttl=ttl,
        )
        return {"source": "FRED_ALFRED", "observed_at": observed, "payload": payload}


class GdeltSource(CachedJsonSource):
    BASE = "https://api.gdeltproject.org/api/v2/doc/doc"

    def headlines(self, query, max_records=50, ttl=300):
        payload, observed = self._get(
            self.BASE,
            params={
                "query": str(query),
                "mode": "ArtList",
                "format": "json",
                "maxrecords": max(1, min(250, int(max_records))),
                "sort": "HybridRel",
            },
            ttl=ttl,
        )
        return {"source": "GDELT_DOC_2", "observed_at": observed, "payload": payload}
