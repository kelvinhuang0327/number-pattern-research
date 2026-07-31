from __future__ import annotations

import json
import re
import shutil
import ssl
import subprocess
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TSL_FRONTEND_PROBE_PATH = ROOT / "data" / "tsl_frontend_probe.json"
TSL_HOME_CACHE_PATH = Path("/tmp/tsl_pre_match.html")
TSL_BUNDLE_CACHE_PATH = Path("/tmp/tsl_index.js")

TSL_HOME_URL = "https://www.sportslottery.com.tw/zh-tw/game/pre-match?sportId=1"
BASEBALL_SPORT_ID = "34731.1"


@dataclass(frozen=True)
class TSLFrontendProbeResult:
    bundle_url: str
    api_endpoints: list[str]
    baseball_market_catalog: list[dict[str, Any]]
    fetched_at: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _fetch_text(url: str) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/javascript,*/*",
        "Referer": "https://www.sportslottery.com.tw/",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, context=_ssl_context(), timeout=10) as response:
            return response.read().decode("utf-8")
    except Exception:
        curl_path = shutil.which("curl")
        if not curl_path:
            raise
        result = subprocess.run(
            [
                "/bin/bash",
                "-lc",
                (
                    f"'{curl_path}' -L -k "
                    f"-H 'User-Agent: {headers['User-Agent']}' "
                    f"-H 'Accept: {headers['Accept']}' "
                    f"-H 'Referer: {headers['Referer']}' "
                    f"'{url}'"
                ),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout


def extract_bundle_url(html: str) -> str:
    match = re.search(r'<script type="module" crossorigin src="([^"]+index-[^"]+\.js)"', html)
    if not match:
        return ""
    src = match.group(1)
    if src.startswith("http://") or src.startswith("https://"):
        return src
    return f"https://www.sportslottery.com.tw{src}"


def extract_api_endpoints(bundle_js: str) -> list[str]:
    endpoints = sorted(
        {
            match.group(0)
            for match in re.finditer(
                r"https://(?:api3rd|blob3rd)\.sportslottery\.com\.tw[^\"]*|/services/content/get|/api/betting/fo/[A-Za-z/${}_-]+",
                bundle_js,
            )
        }
    )
    return endpoints


def extract_baseball_market_catalog(bundle_js: str) -> list[dict[str, Any]]:
    pattern = re.compile(
        r'V\("34731\.1","([^"]+)",U\.([A-Za-z0-9_]+)(?:,Z\.([A-Za-z0-9_]+)|,null)?'
        r'(?:,([0-9]+),([0-9]+))?(?:,"([^"]+)")?\)'
    )
    catalog: list[dict[str, Any]] = []
    for match in pattern.finditer(bundle_js):
        market_type_id, kind, filter_key, pre_rank, live_rank, type_key = match.groups()
        catalog.append(
            {
                "sport_id": BASEBALL_SPORT_ID,
                "market_type_id": market_type_id,
                "kind": kind,
                "filter_key": filter_key or "",
                "show_on_pre_list": int(pre_rank) if pre_rank is not None else 0,
                "show_on_live_list": int(live_rank) if live_rank is not None else 0,
                "type_key": type_key or "",
            }
        )
    return catalog


def probe_tsl_frontend() -> TSLFrontendProbeResult:
    try:
        html = _fetch_text(TSL_HOME_URL)
    except Exception:
        if not TSL_HOME_CACHE_PATH.exists():
            raise
        html = TSL_HOME_CACHE_PATH.read_text(encoding="utf-8")

    bundle_url = extract_bundle_url(html)
    if not bundle_url and TSL_BUNDLE_CACHE_PATH.exists():
        bundle_url = "cached:/tmp/tsl_index.js"
    if not bundle_url:
        raise RuntimeError("Unable to locate TSL frontend bundle URL")

    try:
        bundle_js = _fetch_text(bundle_url) if not bundle_url.startswith("cached:") else ""
    except Exception:
        if not TSL_BUNDLE_CACHE_PATH.exists():
            raise
        bundle_js = TSL_BUNDLE_CACHE_PATH.read_text(encoding="utf-8")
        bundle_url = "cached:/tmp/tsl_index.js"
    if not bundle_js and TSL_BUNDLE_CACHE_PATH.exists():
        bundle_js = TSL_BUNDLE_CACHE_PATH.read_text(encoding="utf-8")

    return TSLFrontendProbeResult(
        bundle_url=bundle_url,
        api_endpoints=extract_api_endpoints(bundle_js),
        baseball_market_catalog=extract_baseball_market_catalog(bundle_js),
        fetched_at=_utc_now(),
    )


def save_tsl_frontend_probe(result: TSLFrontendProbeResult) -> dict[str, Any]:
    payload = {
        "bundle_url": result.bundle_url,
        "api_endpoints": result.api_endpoints,
        "baseball_market_catalog": result.baseball_market_catalog,
        "fetched_at": result.fetched_at,
    }
    TSL_FRONTEND_PROBE_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


if __name__ == "__main__":
    save_tsl_frontend_probe(probe_tsl_frontend())
