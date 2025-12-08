"""Simple viewer server with a legal-details endpoint."""

from __future__ import annotations

import json
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urljoin, urlparse
from typing import Any, Dict

import httpx

ROOT_DIR = Path(__file__).resolve().parent
sys.path.append(str(ROOT_DIR.parent))

from config import get_api_base_url
from legal_details import save_legal_details


DATA_DIR = ROOT_DIR.parent / "data" / "summaries"


def build_legal_markdown(year: int, month: int, active: int, closed: str) -> str:
    closed_text = (closed or "").strip() or "_No closed litigations provided._"
    return (
        f"# Legal Details for {year}-{month:02d}\n\n"
        f"- Active litigations: {active}\n\n"
        "## Closed Litigations\n"
        f"{closed_text}\n"
    )



# ---------------------------------------------------------------------------
# Application-specific imports / configuration
# ---------------------------------------------------------------------------

# You should define these in your application:
#
# ROOT_DIR: directory from which static assets are served
# DATA_DIR: directory where legal details are written
# get_api_base_url(): returns the base URL of the upstream API; e.g.
#     - "https://example.com/vuecrest/"
#     - "http://localhost:8086/"
# build_legal_markdown(year, month, active, closed) -> str
# save_legal_details(summary, year, month, base_dir) -> pathlib.Path
#
# Example placeholders:
#
# from pathlib import Path
# ROOT_DIR = Path(__file__).parent / "static"
# DATA_DIR = Path(__file__).parent / "data"
# def get_api_base_url() -> str: ...
# def build_legal_markdown(year: int, month: int, active: int, closed: str) -> str: ...
# def save_legal_details(summary: str, year: int, month: int, base_dir) -> Path: ...


class ViewerHandler(SimpleHTTPRequestHandler):
    """Serve the viewer assets and accept legal detail submissions."""

    def __init__(self, *args, **kwargs) -> None:
        # Serve static assets from ROOT_DIR
        super().__init__(*args, directory=str(ROOT_DIR), **kwargs)

    # ------------------------------------------------------------------ #
    # Utility helpers
    # ------------------------------------------------------------------ #

    def _set_cors(self) -> None:
        """Set permissive CORS headers for XHR from the viewer UI."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def _respond_json(self, status: int, payload: Dict[str, Any]) -> None:
        """Send a JSON response with CORS headers."""
        self.send_response(status)
        self._set_cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def _full_api_url(self) -> str:
        """
        Combine API_BASE_URL with the incoming path to form an absolute URL.

        This preserves the original path and query string, so a request to:

            /api/legal-details?foo=bar

        becomes:

            <API_BASE_URL>/api/legal-details?foo=bar
        """
        base = get_api_base_url()
        parsed = urlparse(self.path)

        # Normalize base to look like a "directory" for urljoin
        base_norm = base.rstrip("/") + "/"
        upstream = urljoin(base_norm, parsed.path.lstrip("/"))

        if parsed.query:
            upstream = upstream + "?" + parsed.query

        return upstream

    def _is_self_url(self, target_url: str) -> bool:
        """
        Return True if target_url resolves to this same HTTP server.

        This is used to avoid proxy loops when API_BASE_URL points
        back at this process (e.g., http://localhost:8086/).
        """
        parsed = urlparse(target_url)

        # What this HTTP server is actually bound to.
        server_host, server_port = self.server.server_address  # type: ignore[attr-defined]

        # server_host may be '' meaning "all interfaces"
        if not server_host:
            server_host = "localhost"

        # parsed.netloc may be "host" or "host:port"
        host, _, port_str = parsed.netloc.partition(":")
        if not host:
            # If no explicit host in the URL, treat as not self
            return False

        if port_str:
            try:
                port = int(port_str)
            except ValueError:
                return False
        else:
            # Default ports by scheme
            if parsed.scheme == "https":
                port = 443
            else:
                port = 80

        # Consider localhost variants and the actual bind address as "self"
        return host in ("localhost", "127.0.0.1", server_host) and port == server_port

    def _proxy_post(self, target_url: str) -> None:
        """Forward the POST body to the configured API_BASE_URL + path."""
        content_length = int(self.headers.get("Content-Length", "0") or 0)
        raw_body = self.rfile.read(content_length)

        # Forward a minimal set of headers; extend as needed (Authorization, Cookie, etc.)
        headers: Dict[str, str] = {}
        if "Content-Type" in self.headers:
            headers["Content-Type"] = self.headers["Content-Type"]

        try:
            resp = httpx.post(target_url, content=raw_body, headers=headers, timeout=10.0)
        except Exception as exc:
            self._respond_json(
                502,
                {
                    "error": f"Upstream POST failed: {exc}",
                    "target": target_url,
                },
            )
            return

        # Relay upstream status and body back to the client
        self.send_response(resp.status_code)
        self._set_cors()
        content_type = resp.headers.get("Content-Type", "application/json")
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(resp.content)

    # ------------------------------------------------------------------ #
    # HTTP method handlers
    # ------------------------------------------------------------------ #

    def do_OPTIONS(self) -> None:
        """
        Handle CORS preflight for /api/* endpoints.

        Nginx is configured as:

            location /vuecrest/ {
                proxy_pass http://10.12.0.24:8086/;
                ...
            }

        Because of the trailing slash, /vuecrest/api/... becomes /api/...
        when it hits this handler, so self.path starts with "/api/".
        """
        if self.path.startswith("/api/"):
            self.send_response(204)
            self._set_cors()
            self.end_headers()
            return
        # Fall back to default behavior for non-API paths
        super().do_OPTIONS()

    def do_POST(self) -> None:
        """
        Route POSTs either to local handler or proxy to upstream API.
        """
        # Only handling one API endpoint for now.
        if self.path.rstrip("/") == "/api/legal-details":
            target_url = self._full_api_url()

            # Avoid proxy loops when API_BASE_URL points to this same server.
            if self._is_self_url(target_url):
                self._handle_legal_details()
            else:
                self._proxy_post(target_url)
            return

        self.send_error(404, "Unknown endpoint")

    # ------------------------------------------------------------------ #
    # Business logic for /api/legal-details
    # ------------------------------------------------------------------ #

    def _handle_legal_details(self) -> None:
        """
        Local implementation of the /api/legal-details endpoint.

        Expects JSON body with fields:
            - year: int
            - month: int (1-12)
            - active_litigation: int (0-10)
            - closed_litigations: str (optional, free text)
        """
        content_length = int(self.headers.get("Content-Length", "0") or 0)
        raw_body = self.rfile.read(content_length)

        try:
            payload = json.loads(raw_body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._respond_json(400, {"error": "Request body must be valid JSON."})
            return

        try:
            year = int(payload.get("year"))
            month = int(payload.get("month"))
            active = int(payload.get("active_litigation"))
        except (TypeError, ValueError):
            self._respond_json(
                400,
                {
                    "error": "Fields year, month, active_litigation are required numbers."
                },
            )
            return

        if not (1 <= month <= 12):
            self._respond_json(400, {"error": "Month must be between 1 and 12."})
            return
        if not (0 <= active <= 10):
            self._respond_json(
                400,
                {"error": "Active litigation must be between 0 and 10."},
            )
            return

        closed = str(payload.get("closed_litigations") or "").strip()
        summary = build_legal_markdown(year, month, active, closed)
        out_path = save_legal_details(summary, year, month, base_dir=DATA_DIR)

        self._respond_json(200, {"path": str(out_path)})

    # Optional: quiet down default logging if desired
    # def log_message(self, format: str, *args: Any) -> None:
    #     return  # comment this out to restore default logging


def run(port: int = 8086) -> None:
    """
    Start the threaded HTTP server.

    With your Nginx config:

        location /vuecrest/ {
            proxy_pass http://10.12.0.24:8086/;
            ...
        }

    the external URL will be:
        https://<host>/vuecrest/

    while this server listens on:
        http://10.12.0.24:8086/
    """
    server_address = ("", port)
    httpd = ThreadingHTTPServer(server_address, ViewerHandler)

    host, actual_port = httpd.server_address
    if not host:
        host = "0.0.0.0"

    print(
        f"Serving report viewer on http://{host}:{actual_port}/ "
        f"(data root: {DATA_DIR})"
    )
    httpd.serve_forever()


if __name__ == "__main__":
    port = 8080
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            sys.exit("Port must be an integer, for example: python server.py 8086")
    run(port=port)
