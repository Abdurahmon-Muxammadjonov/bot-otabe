"""HTTP server: health-check, Telegram Mini App sahifasi va lead API.

Railway/Render konteynerni PORT orqali "tirik"ligini tekshiradi - bu server
shu ishni bajaradi VA Mini App (sotuv auditi) sahifasini xizmat qiladi:

    GET  /            -> Portfolio sayt (SITE_URL dan olinadi, zaxira: webapp/site.html)
    GET  /audit       -> Sotuv auditi Mini App (webapp/index.html)
    GET  /health      -> "OK" (platforma health-check)
    GET  /api/audit   -> savollar bazasi (JSON)
    POST /api/lead    -> audit natijasi + kontakt -> zayavka (initData imzosi bilan)

Faqat standart kutubxona. Threading server - bir vaqtda bir necha so'rovga
xizmat qiladi; Storage/Notifier o'zi thread-safe.
"""

from __future__ import annotations

import gzip
import json
import logging
import re
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlsplit

from . import audit, texts as T
from .audit import AuditError, WEBAPP_DIR
from .service import Service, USER_BOT
from .telegram import safe_send
from .utils import esc, restart_keyboard
from .validators import clean_name, normalize_phone, pretty_phone

log = logging.getLogger(__name__)

MAX_BODY = 64 * 1024
COMPANY_MAX = 80
SITE_TTL = 600          # Netlify'dan sayt necha soniyada bir yangilanadi
SITE_FETCH_TIMEOUT = 15
GZIP_MIN = 1024

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}

# Mini App sahifasi kesh - fayl o'zgarsa qayta o'qiladi.
_page_cache: Dict[str, Any] = {}
_page_lock = threading.Lock()


def _read_page() -> str:
    path = WEBAPP_DIR / "index.html"
    with _page_lock:
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return "<h1>Mini App topilmadi</h1><p>webapp/index.html yo'q.</p>"
        bank_mtime = audit.AUDIT_PATH.stat().st_mtime if audit.AUDIT_PATH.exists() else 0
        key = (mtime, bank_mtime)
        if _page_cache.get("key") != key:
            html = path.read_text(encoding="utf-8")
            # Savollar bazasini sahifaga ichkaridan joylaymiz - qo'shimcha so'rov shart emas.
            try:
                bank_json = json.dumps(audit.load_bank(), ensure_ascii=False)
            except AuditError:
                bank_json = "null"
            html = html.replace("/*__AUDIT_DATA__*/null", bank_json, 1)
            _page_cache.update(key=key, html=html)
        return _page_cache["html"]


def _render_page(bot_username: str) -> bytes:
    """Sahifaga bot username'ini joylaydi (brauzerda ochilganda t.me havolasi uchun)."""
    safe = "".join(ch for ch in bot_username if ch.isalnum() or ch == "_")
    return _read_page().replace("/*__BOT__*/", safe, 1).encode("utf-8")


# ------------------------------------------------------------- sayt
# Portfolio sayt Mini App'ning bosh sahifasi. Manba - SITE_URL (Netlify): sayt
# o'sha yerda tahrirlanadi, bot uni vaqti-vaqti bilan olib, Telegram uchun
# moslab beradi. Netlify javob bermasa - webapp/site.html nusxasi.
_site_cache: Dict[str, Any] = {}
_site_lock = threading.Lock()

# Sayt ichiga qo'shiladigan Telegram moslashuvi: SDK, expand, audit tugmalari
# /audit ga (bir oynada, initData saqlanib qoladi), t.me havolalari Telegram ichida.
SITE_PATCH = """
<script src="https://telegram.org/js/telegram-web-app.js?58"></script>
<script>
(function(){
  var tg = window.Telegram && window.Telegram.WebApp;
  if (tg) { try { tg.ready(); tg.expand(); } catch (e) {} }
  var hash = location.hash || '';
  // Telegram bergan #tgWebAppData=... hash SDK tomonidan o'qib olindi (sessionStorage'da
  // saqlanadi) - saytning o'z skripti uni CSS selektor deb o'qimasligi uchun tozalaymiz.
  if (/tgWebApp/.test(hash)) { try { history.replaceState(null, '', location.pathname + location.search); } catch (e) {} }
  function patch(){
    document.querySelectorAll('[data-audit], a[href*="musical-sopapillas"]').forEach(function(a){
      a.href = '/audit' + hash; a.removeAttribute('target');
    });
    document.querySelectorAll('a[href^="https://t.me/"], a[href^="tg://"]').forEach(function(a){
      if (!tg || !tg.openTelegramLink || a.dataset.tgPatched) return;
      a.dataset.tgPatched = '1';
      a.addEventListener('click', function(e){ e.preventDefault(); tg.openTelegramLink(a.href); });
    });
  }
  patch(); setTimeout(patch, 300); window.addEventListener('load', patch);
})();
</script>
"""

_NETLIFY_HUD_RE = re.compile(r"<script[^>]*\.netlify/scripts/hud[^>]*></script>", re.I)
_NETLIFY_META_RE = re.compile(r"<meta name=\"(?:hosting-provider|netlify-deploy)\"[^>]*>\s*", re.I)


def _patch_site(html: str) -> str:
    html = _NETLIFY_HUD_RE.sub("", html)
    html = _NETLIFY_META_RE.sub("", html)
    if "</body>" in html:
        html = html.replace("</body>", SITE_PATCH + "</body>", 1)
    else:
        html += SITE_PATCH
    return html


def _site_snapshot() -> Optional[str]:
    path = WEBAPP_DIR / "site.html"
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _fetch_site(url: str) -> Optional[str]:
    try:
        request = urllib.request.Request(
            url, headers={"User-Agent": "ZayavkaBot/1.0 (+mini-app mirror)", "Accept": "text/html"}
        )
        with urllib.request.urlopen(request, timeout=SITE_FETCH_TIMEOUT) as response:
            raw = response.read(4 * 1024 * 1024)
        html = raw.decode("utf-8", "replace")
        if "<html" not in html.lower():
            return None
        return html
    except Exception as exc:  # noqa: BLE001 - tarmoq/HTTP xatolari
        log.warning("Sayt (%s) olinmadi: %s", url, exc)
        return None


def site_page(site_url: str) -> Optional[bytes]:
    """Patch qilingan sayt sahifasi (kesh: SITE_TTL). Sayt umuman yo'q bo'lsa None."""
    now = time.time()
    with _site_lock:
        cached = _site_cache.get("body")
        if cached is not None and now - _site_cache.get("at", 0) < SITE_TTL:
            return cached
        html = _fetch_site(site_url) if site_url else None
        if html is not None:
            _site_cache.update(body=_patch_site(html).encode("utf-8"), at=now, source="remote")
            return _site_cache["body"]
        if cached is not None:
            # Netlify vaqtincha javob bermadi - eski keshni yana SITE_TTL saqlaymiz.
            _site_cache["at"] = now
            return cached
        snapshot = _site_snapshot()
        if snapshot is None:
            return None
        _site_cache.update(body=_patch_site(snapshot).encode("utf-8"), at=now, source="snapshot")
        return _site_cache["body"]


def prefetch_site(site_url: str) -> None:
    """Birinchi ochilish sekin bo'lmasin - saytni fonda oldindan olib qo'yamiz."""
    def run() -> None:
        body = site_page(site_url)
        if body is not None:
            log.info(
                "Sayt tayyor (%s, %d KB)", _site_cache.get("source", "?"), len(body) // 1024
            )

    threading.Thread(target=run, name="site-prefetch", daemon=True).start()


class LeadHandler(BaseHTTPRequestHandler):
    """Bitta so'rovga xizmat qiladi. `server.service` orqali botga ulanadi."""

    server_version = "ZayavkaBot/1.0"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    # ------------------------------------------------------------- javoblar
    def _send(self, status: int, body: bytes, content_type: str, cache: str = "no-store") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        accepts = self.headers.get("Accept-Encoding", "")
        if len(body) >= GZIP_MIN and "gzip" in accepts and content_type.startswith("text/"):
            body = gzip.compress(body, compresslevel=6)
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Vary", "Accept-Encoding")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        for key, value in SECURITY_HEADERS.items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def _text(self, status: int, text: str) -> None:
        self._send(status, text.encode("utf-8"), "text/plain; charset=utf-8")

    # ---------------------------------------------------------------- GET
    def do_GET(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path.rstrip("/") or "/"
        service: Service = self.server.service  # type: ignore[attr-defined]
        if path == "/":
            body = site_page(service.config.site_url)
            if body is None:
                # Sayt yo'q - bosh sahifa auditning o'zi.
                body = _render_page(service.apis[USER_BOT].username)
            self._send(200, body, "text/html; charset=utf-8", cache="no-cache")
        elif path in ("/audit", "/app", "/index.html"):
            username = service.apis[USER_BOT].username
            self._send(200, _render_page(username), "text/html; charset=utf-8", cache="no-cache")
        elif path in ("/health", "/healthz", "/ping"):
            self._text(200, "OK - bot ishlayapti")
        elif path in ("/api/audit", "/audit.json"):
            try:
                body = json.dumps(audit.load_bank(), ensure_ascii=False).encode("utf-8")
            except AuditError as exc:
                self._json(500, {"ok": False, "error": str(exc)})
                return
            self._send(200, body, "application/json; charset=utf-8", cache="public, max-age=300")
        elif path == "/favicon.ico":
            self._send(204, b"", "image/x-icon", cache="public, max-age=86400")
        else:
            self._text(404, "Topilmadi")

    def do_HEAD(self) -> None:  # noqa: N802
        self.do_GET()

    # ---------------------------------------------------------------- POST
    def do_POST(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path.rstrip("/")
        if path != "/api/lead":
            self._json(404, {"ok": False, "error": "Topilmadi"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_BODY:
            self._json(413, {"ok": False, "error": "So'rov hajmi noto'g'ri"})
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._json(400, {"ok": False, "error": "JSON noto'g'ri"})
            return
        if not isinstance(payload, dict):
            self._json(400, {"ok": False, "error": "JSON noto'g'ri"})
            return

        service: Service = self.server.service  # type: ignore[attr-defined]
        try:
            status, result = handle_lead(service, payload)
        except AuditError as exc:
            status, result = 400, {"ok": False, "error": str(exc)}
        except Exception:  # noqa: BLE001 - bitta xato serverni o'ldirmasin
            log.exception("Mini App: lead qayta ishlashda kutilmagan xato")
            status, result = 500, {"ok": False, "error": "Server xatosi. Birozdan keyin urinib ko'ring."}
        self._json(status, result)

    def log_message(self, fmt: str, *args: Any) -> None:  # jurnalni bosmaydi
        if self.command == "POST":
            log.info("web: %s %s", self.command, fmt % args)


# ------------------------------------------------------------------- lead
def handle_lead(service: Service, payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Mini App'dan kelgan audit natijasini tekshiradi va zayavka yaratadi."""
    config = service.config

    # 1) Kim yuboryapti? initData imzosi bot tokeni bilan tekshiriladi.
    init_data = payload.get("initData")
    if not isinstance(init_data, str) or not init_data:
        return 401, {
            "ok": False,
            "code": "no_telegram",
            "error": "Ilovani Telegram orqali oching - shunda natija botga ulanadi.",
        }
    try:
        tg_user = audit.verify_init_data(init_data, config.user_bot_token)
    except AuditError as exc:
        return 401, {"ok": False, "code": "bad_signature", "error": str(exc)}
    user_id = int(tg_user["id"])

    # 2) Kontakt maydonlari - botdagi bilan bir xil tekshiruv.
    name, error = clean_name(str(payload.get("name") or ""))
    if not name:
        return 400, {"ok": False, "field": "name", "error": _strip_html(T.NAME_ERRORS.get(error, T.NAME_ERRORS["empty"]))}
    phone, error = normalize_phone(str(payload.get("phone") or ""))
    if not phone:
        return 400, {"ok": False, "field": "phone", "error": _strip_html(T.PHONE_ERRORS.get(error, T.PHONE_ERRORS["empty"]))}
    company = " ".join(str(payload.get("company") or "").split())[:COMPANY_MAX]

    avg_check: Optional[int] = None
    raw_check = payload.get("avg_check")
    if isinstance(raw_check, (int, float)) and not isinstance(raw_check, bool) and 0 < raw_check < 1e13:
        avg_check = int(raw_check)

    # 3) Ball serverda qayta hisoblanadi.
    result = audit.compute(payload.get("profile"), payload.get("answers"))

    # 4) Spam/limit - botdagi qoidalar.
    limit = _limit_message(service, user_id)
    if limit:
        return 429, {"ok": False, "code": "limit", "error": limit}

    # 5) Saqlash va adminlarga uzatish.
    from .admin_handlers import display_name  # aylanma importdan qochish

    phone_source = "webapp_contact" if payload.get("phone_source") == "contact" else "webapp"
    application = service.storage.add_application(
        user_id=user_id,
        chat_id=user_id,
        name=name,
        phone=phone,
        username=tg_user.get("username") or "",
        full_name=display_name(tg_user),
        language_code=tg_user.get("language_code") or "",
        phone_source=phone_source,
        source="webapp",
        company=company,
        audit=audit.summary_for_storage(result, avg_check),
    )
    service.storage.clear_session(service.session_key(USER_BOT, user_id))
    service.notifier.enqueue(application)
    log.info(
        "Mini App: zayavka #%s (user %s, ball %s)", application["id"], user_id, result["score"]
    )

    # 6) Mijozga hisobotni chatga yuboramiz (fon oqimida - javob kechikmasin).
    threading.Thread(
        target=_send_user_report,
        args=(service, application, result, name, phone),
        name="webapp-report",
        daemon=True,
    ).start()

    return 200, {
        "ok": True,
        "id": application["id"],
        "score": result["score"],
        "band": result["band"],
        "bot": service.apis[USER_BOT].username,
    }


def _send_user_report(
    service: Service, application: Dict[str, Any], result: Dict[str, Any], name: str, phone: str
) -> None:
    api = service.apis.get(USER_BOT)
    if api is None:
        return
    chat_id = int(application["chat_id"])
    text = T.WEBAPP_SUCCESS.format(
        id=application["id"], name=esc(name), phone=esc(pretty_phone(phone)),
        score=result["score"], band=esc(result["band"]),
    )
    if service.config.contact_info:
        text += T.SUCCESS_CONTACT.format(contact=esc(service.config.contact_info))
    if safe_send(api, chat_id, text, reply_markup=restart_keyboard(T.BTN_NEW_REQUEST)) is None:
        log.warning("Mini App: #%s - mijozga tasdiq yuborilmadi", application["id"])
        return
    for chunk in audit.render_user_report(result, service.config.company_name):
        if safe_send(api, chat_id, chunk) is None:
            break
        time.sleep(0.3)


def _limit_message(service: Service, user_id: int) -> Optional[str]:
    config = service.config
    if config.submit_cooldown_sec > 0:
        last = service.storage.last_submission_ts(user_id)
        waited = time.time() - last
        if last and waited < config.submit_cooldown_sec:
            return _strip_html(
                T.COOLDOWN.format(seconds=int(config.submit_cooldown_sec - waited) + 1)
            )
    if config.max_per_day > 0:
        if service.storage.count_recent_by_user(user_id, 24 * 3600) >= config.max_per_day:
            return _strip_html(T.DAILY_LIMIT.format(limit=config.max_per_day))
    return None


def _strip_html(text: str) -> str:
    import re

    return re.sub(r"<[^>]+>", "", text).replace("\n", " ").strip()


# ----------------------------------------------------------------- server
def start_web_server(port: int, service: Service) -> None:
    """PORT ustida daemon oqimda serverni ishga tushiradi (bloklamaydi)."""

    def run() -> None:
        try:
            server = ThreadingHTTPServer(("0.0.0.0", port), LeadHandler)
        except OSError as exc:
            log.warning("Web server ishga tushmadi (port %s): %s", port, exc)
            return
        server.daemon_threads = True
        server.service = service  # type: ignore[attr-defined]
        log.info("Web server tayyor: 0.0.0.0:%s (health-check + sayt + audit)", port)
        server.serve_forever()

    threading.Thread(target=run, name="web", daemon=True).start()
    prefetch_site(service.config.site_url)
