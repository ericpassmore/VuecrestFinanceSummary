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
        if self.path.rstrip("/") == "/api/legal-details":
            # Always handle locally
            self._handle_legal_details()
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
