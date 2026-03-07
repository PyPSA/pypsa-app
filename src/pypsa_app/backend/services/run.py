"""HTTP client for the smk-executor service."""

import logging
from collections.abc import Iterator
from http import HTTPStatus
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0


class SmkExecutorError(Exception):
    """Error communicating with smk-executor service."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class SmkExecutorClient:
    """Talks to smk-executor over HTTP using httpx."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> dict:
        url = f"{self.base_url}{path}"
        try:
            response = httpx.request(method, url, json=json, timeout=timeout)
        except httpx.ConnectError as e:
            raise SmkExecutorError(503, "smk-executor service is unreachable") from e
        except httpx.TimeoutException as e:
            raise SmkExecutorError(504, "smk-executor request timed out") from e

        if response.status_code == HTTPStatus.NOT_FOUND:
            raise SmkExecutorError(HTTPStatus.NOT_FOUND, "Job not found on smk-executor")
        if response.status_code >= HTTPStatus.BAD_REQUEST:
            detail = response.text[:500]
            raise SmkExecutorError(502, f"smk-executor error: {detail}")

        return response.json()

    def health_check(self) -> dict:
        return self._request("GET", "/health")

    def list_jobs(self) -> list[dict]:
        """Fetch all jobs."""
        result = self._request("GET", "/jobs")
        return result.get("jobs", [])

    def submit_job(self, payload: dict) -> dict:
        return self._request("POST", "/jobs", json=payload)

    def get_job(self, job_id: str) -> dict:
        return self._request("GET", f"/jobs/{job_id}")

    def get_job_outputs(self, job_id: str) -> list[dict]:
        result = self._request("GET", f"/jobs/{job_id}/outputs")
        return result.get("files", [])

    def cancel_job(self, job_id: str) -> dict:
        return self._request("POST", f"/jobs/{job_id}/cancel")

    def delete_job(self, job_id: str) -> dict:
        return self._request("DELETE", f"/jobs/{job_id}")

    def _proxy_stream(self, path: str) -> Iterator[bytes]:
        """Forward a streaming response without buffering.

        Status is checked eagerly before yielding so that HTTP errors
        propagate as exceptions before StreamingResponse starts writing.
        """
        url = f"{self.base_url}{path}"
        try:
            client = httpx.Client(timeout=None)  # noqa: S113
            response = client.send(client.build_request("GET", url), stream=True)
        except httpx.ConnectError as e:
            raise SmkExecutorError(503, "smk-executor service is unreachable") from e

        if response.status_code == HTTPStatus.NOT_FOUND:
            response.close()
            client.close()
            raise SmkExecutorError(HTTPStatus.NOT_FOUND, "Not found on smk-executor")
        if response.status_code >= HTTPStatus.BAD_REQUEST:
            response.close()
            client.close()
            raise SmkExecutorError(502, "smk-executor streaming error")

        def generate() -> Iterator[bytes]:
            try:
                yield from response.iter_bytes()
            finally:
                response.close()
                client.close()

        return generate()

    def subscribe_job_logs(self, job_id: str) -> Iterator[bytes]:
        """Subscribe to live SSE log stream (open connection)."""
        return self._proxy_stream(f"/jobs/{job_id}/logs")

    def get_job_logs_text(self, job_id: str) -> Iterator[bytes]:
        """Get logs as plain text, stripping SSE framing."""
        for chunk in self._proxy_stream(f"/jobs/{job_id}/logs"):
            for line in chunk.decode("utf-8", errors="replace").splitlines(True):
                if line.startswith("data: "):
                    yield line[6:].encode()
                elif line.startswith("data:"):
                    yield line[5:].encode()
                elif line.startswith("event:"):
                    continue
                elif line.strip() == "":
                    continue

    def download_job_output(self, job_id: str, path: str) -> Iterator[bytes]:
        """Download an output file without buffering into memory."""
        return self._proxy_stream(f"/jobs/{job_id}/outputs/{path}")

    def download_job_output_to_file(self, job_id: str, path: str, dest: Path) -> None:
        """Download an output file to a local path."""
        url = f"{self.base_url}/jobs/{job_id}/outputs/{path}"
        try:
            with httpx.stream("GET", url, timeout=300.0) as response:
                if response.status_code >= HTTPStatus.BAD_REQUEST:
                    raise SmkExecutorError(
                        502, f"smk-executor download error: {response.status_code}"
                    )
                with dest.open("wb") as f:
                    for chunk in response.iter_bytes():
                        f.write(chunk)
        except httpx.ConnectError as e:
            raise SmkExecutorError(503, "smk-executor service is unreachable") from e
        except httpx.TimeoutException as e:
            raise SmkExecutorError(504, "smk-executor download timed out") from e
