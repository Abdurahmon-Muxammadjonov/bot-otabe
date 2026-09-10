"""Railway/Render kabi platformalar uchun oddiy HTTP health-check server.

Bu platformalar konteyner "tirik"ligini HTTP porti orqali tekshiradi. Bizning
bot esa long-polling worker (web server emas). Shu sabab PORT berilgan bo'lsa,
javob qaytaradigan mitti server ishga tushiramiz - aks holda platforma botni
"ishlamayapti" deb qayta-qayta o'chirib tashlaydi.
"""

from __future__ import annotations

import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

log = logging.getLogger(__name__)


class _Handler(BaseHTTPRequestHandler):
    def _ok(self) -> None:
        body = b"OK - bot ishlayapti"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        self._ok()

    def do_HEAD(self) -> None:  # noqa: N802
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args: object) -> None:  # jurnalers'ni bosmaydi
        return


def start_health_server(port: int) -> None:
    """PORT ustida daemon oqimda health-check server ishga tushiradi."""

    def run() -> None:
        try:
            server = ThreadingHTTPServer(("0.0.0.0", port), _Handler)
        except OSError as exc:
            log.warning("Health-check server ishga tushmadi (port %s): %s", port, exc)
            return
        log.info("Health-check server tayyor: 0.0.0.0:%s", port)
        server.serve_forever()

    threading.Thread(target=run, name="health", daemon=True).start()
