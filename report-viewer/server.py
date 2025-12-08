"""Simple viewer server with a legal-details endpoint."""

from __future__ import annotations

import json
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict

ROOT_DIR = Path(__file__).resolve().parent
sys.path.append(str(ROOT_DIR.parent))

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


class ViewerHandler(SimpleHTTPRequestHandler):
    """Serve the viewer assets and accept legal detail submissions."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, directory=str(ROOT_DIR), **kwargs)

    def _set_cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def _respond_json(self, status: int, payload: Dict[str, Any]) -> None:
        self.send_response(status)
        self._set_cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def do_OPTIONS(self) -> None:
        if self.path.startswith("/api/"):
            self.send_response(204)
            self._set_cors()
            self.end_headers()
            return
        super().do_OPTIONS()

    def do_POST(self) -> None:
        if self.path.rstrip("/") == "/api/legal-details":
            self._handle_legal_details()
            return
        self.send_error(404, "Unknown endpoint")

    def _handle_legal_details(self) -> None:
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
            self._respond_json(400, {"error": "Fields year, month, active_litigation are required numbers."})
            return

        if not (1 <= month <= 12):
            self._respond_json(400, {"error": "Month must be between 1 and 12."})
            return
        if not (0 <= active <= 10):
            self._respond_json(400, {"error": "Active litigation must be between 0 and 10."})
            return

        closed = str(payload.get("closed_litigations") or "").strip()
        summary = build_legal_markdown(year, month, active, closed)
        out_path = save_legal_details(summary, year, month, base_dir=DATA_DIR)

        self._respond_json(200, {"path": str(out_path)})


def run(port: int = 8080) -> None:
    server_address = ("", port)
    httpd = ThreadingHTTPServer(server_address, ViewerHandler)
    print(f"Serving report viewer at http://localhost:{port}/ (data root: {DATA_DIR})")
    httpd.serve_forever()


if __name__ == "__main__":
    port = 8080
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            sys.exit("Port must be an integer, for example: python server.py 8086")
    run(port=port)
