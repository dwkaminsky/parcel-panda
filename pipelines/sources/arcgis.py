from __future__ import annotations

from typing import Any, Protocol

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


HTTP_TIMEOUT = (5, 45)
USER_AGENT = "ParcelPandaDataPipeline/1.0"


class HTTPSession(Protocol):
    def get(self, url: str, **kwargs: Any) -> Any: ...


class SourceResponseError(RuntimeError):
    """Raised when a source responds successfully at HTTP level but rejects a query."""


def new_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"Accept": "application/json", "User-Agent": USER_AGENT})
    retries = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
    )
    session.mount("https://", HTTPAdapter(max_retries=retries))
    return session


def fetch_arcgis_features(
    session: HTTPSession,
    layer_url: str,
    *,
    where: str,
    limit: int,
    page_size: int,
    order_by: str,
    out_fields: str = "*",
) -> list[dict[str, Any]]:
    """Fetch an ArcGIS feature layer in deterministic, bounded pages."""
    features: list[dict[str, Any]] = []
    offset = 0
    max_page_size = max(1, page_size)

    while len(features) < limit:
        requested = min(max_page_size, limit - len(features))
        response = session.get(
            f"{layer_url.rstrip('/')}/query",
            params={
                "f": "json",
                "where": where,
                "outFields": out_fields,
                "returnGeometry": "true",
                "outSR": 4326,
                "orderByFields": order_by,
                "resultOffset": offset,
                "resultRecordCount": requested,
            },
            timeout=HTTP_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise SourceResponseError("ArcGIS response was not a JSON object")
        if payload.get("error"):
            error = payload["error"]
            message = error.get("message") if isinstance(error, dict) else str(error)
            raise SourceResponseError(f"ArcGIS query failed: {message or 'unknown error'}")

        page = payload.get("features")
        if not isinstance(page, list):
            raise SourceResponseError("ArcGIS response did not include a features array")
        valid_page = [feature for feature in page if isinstance(feature, dict)]
        features.extend(valid_page[: limit - len(features)])

        if not page or len(page) < requested or payload.get("exceededTransferLimit") is False:
            break
        offset += len(page)

    return features
