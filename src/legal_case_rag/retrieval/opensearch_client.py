from __future__ import annotations

import base64
import json
import ssl
import urllib.error
import urllib.request
from typing import Any


class OpenSearchClient:
    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        verify_ssl: bool = False,
        timeout: int = 30,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        auth = f"{username}:{password}".encode("utf-8")
        self.auth_header = "Basic " + base64.b64encode(auth).decode("ascii")
        self.context = ssl.create_default_context()
        if not verify_ssl:
            self.context = ssl._create_unverified_context()

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = {
            "Authorization": self.auth_header,
            "Content-Type": "application/json",
        }
        data = None
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout,
                context=self.context,
            ) as response:
                content = response.read().decode("utf-8")
                return json.loads(content) if content else {}
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenSearch HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"OpenSearch connection failed: {exc}") from exc
