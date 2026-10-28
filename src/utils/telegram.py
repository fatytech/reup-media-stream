from datetime import datetime
from dataclasses import dataclass

import requests
from loguru import logger


def _now() -> str:
    return datetime.now().strftime("%H:%M · %d/%m/%Y")


def _fmt_followers(n: int) -> str:
    return f"{n:,}"


@dataclass
class AccountResult:
    outcome: str                # ok | fail | skip | no_video | token_expired
    page_id: str = ""
    page_name: str = ""
    tiktok_username: str = ""
    description: str = ""
    reel_url: str = ""
    error: str = ""
    uploaded: int = 0
    total: int = 0
    success_count: int = 0
    failed_count: int = 0
    queue_done: bool = False
    translate_warn: str = ""
    followers_count: int = 0


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str):
        self._url = f"https://api.telegram.org/bot{token}/sendMessage"
        self._chat_id = chat_id
        self._enabled = bool(token and chat_id)

    def _send(self, text: str) -> None:
        if not self._enabled:
            return
        try:
            requests.post(
                self._url,
                json={
                    "chat_id": self._chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                timeout=10,
            )
        except Exception as e:
            logger.warning(f"Telegram send failed: {e}")

    def session_report(self, results: list[AccountResult], active: int, vps_id: str = "") -> None:
        header = f"📊 <b>Session Report</b> | {_now()}"
        if vps_id:
            header += f" | 🖥 <code>{vps_id}</code>"
        lines = [header, ""]

        if active == 0:
            lines.append("👥 Không có account nào active")
            self._send("\n".join(lines))
            return

        for i, r in enumerate(results, 1):
            followers = _fmt_followers(r.followers_count)
            lines.append(f"<b>[{i}] {r.page_name}</b> <code>({r.page_id})</code>  👥 {followers}")
            lines.append(f"🎵 @{r.tiktok_username}")

            if r.outcome == "token_expired":
                lines.append("⚠️ Token hết hạn — cập nhật trong Sheet")
            elif r.outcome == "no_video":
                lines.append("📭 Không có video nào để upload")
            elif r.outcome == "ok":
                lines.append(f"✅ Upload thành công → <a href='{r.reel_url}'>Xem Reel</a>")
                lines.append(f"📝 {r.description}")
                lines.append(f"📊 DB: {r.uploaded}/{r.total}  ✅{r.success_count}  ❌{r.failed_count}")
            elif r.outcome == "skip":
                lines.append("⏭ Video bị bỏ qua (kích thước không đủ)")
                lines.append(f"📊 DB: {r.uploaded}/{r.total}  ✅{r.success_count}  ❌{r.failed_count}")
            elif r.outcome == "fail":
                lines.append(f"❌ Upload thất bại")
                lines.append(f"💬 {r.error}")
                lines.append(f"📊 DB: {r.uploaded}/{r.total}  ✅{r.success_count}  ❌{r.failed_count}")

            if r.queue_done:
                lines.append("📭 Queue hết — cần crawl thêm video mới")
            if r.translate_warn:
                lines.append(r.translate_warn)

            lines.append("")

        # Summary line
        ok       = sum(1 for r in results if r.outcome == "ok")
        failed   = sum(1 for r in results if r.outcome == "fail")
        tok_exp  = sum(1 for r in results if r.outcome == "token_expired")
        skipped  = sum(1 for r in results if r.outcome == "skip")
        no_video = sum(1 for r in results if r.outcome == "no_video")

        parts = [f"👥 {active}"]
        if ok:       parts.append(f"✅{ok}")
        if failed:   parts.append(f"❌{failed}")
        if tok_exp:  parts.append(f"⚠️{tok_exp}")
        if skipped:  parts.append(f"⏭{skipped}")
        if no_video: parts.append(f"📭{no_video}")
        lines.append("  ".join(parts))

        self._send("\n".join(lines))
