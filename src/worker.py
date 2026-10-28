import json
import os
import random
import re
import tempfile
from loguru import logger

from src.api.facebook import FacebookAPI
from src.api.sheets import AppScriptLoader, RowItem
from src.config.settings import Settings
from src.crawler.tiktok import TiktokCrawler
from src.db.database import ReupDB
from src.models.reup_item import ReupItem
from src.models.run_configs import RunConfigs
from src.utils.helpers import build_description
from src.utils.telegram import TelegramNotifier, AccountResult
from src.utils.video import download_video, process_video, validate_video

try:
    from src.utils.ai import translate_desc
    _TRANSLATE_AVAILABLE = True
except ImportError:
    _TRANSLATE_AVAILABLE = False

_SKIP = "SKIP"


class ReelsReupWorker:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.sheets = AppScriptLoader(settings.appscript_url, settings.sheet_id, settings.sheet_name)
        self.tiktok = TiktokCrawler(settings.rapidapi_key)
        self.tg = TelegramNotifier(settings.telegram_token, settings.telegram_chat_id)

    def run_session(self) -> None:
        logger.info(f"=== Session started | VPS: {self.settings.vps_id} ===")
        rows = self.sheets.fetch_row_items()
        active = [r for r in rows if r.vps == self.settings.vps_id and r.status == "running"]
        logger.info(f"Active accounts: {len(active)}")

        results: list[AccountResult] = []
        for row in active:
            try:
                result = self._process_account(row)
            except Exception as e:
                logger.error(f"Unhandled error: {e}")
                result = AccountResult(outcome="fail", error=str(e))
            results.append(result)

        self.tg.session_report(results, active=len(active), vps_id=self.settings.vps_id)
        logger.info("=== Session done ===")

    def _process_account(self, row: RowItem) -> AccountResult:
        fb = FacebookAPI(row.token)

        page_info = fb.get_page_info()
        if page_info is None:
            logger.warning(f"Token invalid/expired (row {row.row})")
            self.sheets.update_status(row, "token_expired")
            return AccountResult(
                outcome="token_expired",
                page_id=f"row={row.row}",
                page_name=f"row={row.row}",
                tiktok_username=",".join(row.tiktok_channels),
            )

        page_id = page_info["id"]
        page_name = page_info.get("name", page_id)
        tiktok_username = ",".join(row.tiktok_channels)
        logger.info(f"[{page_name}] Processing @{tiktok_username}")

        db = ReupDB(self.settings.db_path)

        uploaded, success, failed = db.count_stats(page_id)
        row.statistic = _build_statistic(page_info, uploaded, success, failed)
        self.sheets.update_statistic(row)

        pending = db.get_pending(page_id)
        if pending:
            logger.info(f"[{page_name}] DB cache: {len(pending)} pending videos")
        else:
            logger.info(f"[{page_name}] No pending in DB, crawling TikTok...")
            pending = self._crawl_and_store(db, row, page_id)

        if not pending:
            logger.info(f"[{page_name}] No pending videos → finish")
            self.sheets.update_status(row, "finish")
            return AccountResult(
                outcome="no_video",
                page_id=page_id, page_name=page_name, tiktok_username=tiktok_username,
            )

        random.shuffle(pending)
        item = pending[0]
        logger.info(f"[{page_name}] Uploading: {item.url[:80]}")

        description = build_description(item.content, row.run_configs)
        description, translate_warn = self._maybe_translate(
            description, row.run_configs.translate_code, page_name
        )

        download_url = self.tiktok.get_direct_url(item.url)
        if not download_url:
            logger.warning(f"[{page_name}] Cannot get download URL for {item.url[:80]}")
            db.update_pin(page_id, item.url, "fail")
            return AccountResult(
                outcome="fail",
                page_id=page_id, page_name=page_name, tiktok_username=tiktok_username,
                error="Không lấy được link download từ TikTok API",
            )

        reel_url, error = self._upload_reel(fb, page_id, row.run_configs, description, download_url)

        db.update_pin(page_id, item.url, reel_url if reel_url else ("skip" if error == _SKIP else "fail"))

        uploaded, success, failed = db.count_stats(page_id)
        total = len(db.get_all(page_id))
        row.statistic = _build_statistic(page_info, uploaded, success, failed)
        self.sheets.update_statistic(row)
        self.sheets.update_last_session(row)

        queue_done = not db.get_pending(page_id)
        if queue_done:
            self.sheets.update_status(row, "finish")

        if reel_url:
            outcome = "ok"
        elif error == _SKIP:
            outcome = "skip"
        else:
            outcome = "fail"

        return AccountResult(
            outcome=outcome,
            page_id=page_id, page_name=page_name, tiktok_username=tiktok_username,
            description=description,
            reel_url=reel_url or "",
            error=error if error != _SKIP else "",
            uploaded=uploaded, total=total,
            success_count=success, failed_count=failed,
            queue_done=queue_done,
            translate_warn=translate_warn,
            followers_count=page_info.get("followers_count") or page_info.get("fan_count", 0),
        )

    def _crawl_and_store(self, db: ReupDB, row: RowItem, page_id: str) -> list[ReupItem]:
        for username in row.tiktok_channels:
            items = self.tiktok.crawl_user_posts(username)
            for item in items:
                db.upsert(page_id, item)
        return db.get_pending(page_id)

    def _maybe_translate(self, description: str, lang: str, page_name: str) -> tuple[str, str]:
        if not lang:
            return description, ""
        if not self.settings.ai_api_key:
            warn = f"⚠️ AI_API_KEY chưa set — bỏ qua dịch ({lang})"
            logger.warning(f"[{page_name}] {warn}")
            return description, warn
        if not _TRANSLATE_AVAILABLE:
            warn = f"⚠️ openai chưa cài — bỏ qua dịch ({lang})"
            logger.warning(f"[{page_name}] {warn}")
            return description, warn
        try:
            text, tags = _split_text_and_tags(description)
            translated = translate_desc(text, lang) if text else ""
            result = f"{translated} {tags}".strip() if tags else translated
            logger.info(f"[{page_name}] Translated → {result[:80]}")
            return result, ""
        except Exception as e:
            warn = f"⚠️ Dịch thất bại ({lang}): {e} — dùng caption gốc"
            logger.error(f"[{page_name}] Translate failed: {e}")
            return description, warn

    def _upload_reel(
        self, fb: FacebookAPI, page_id: str, configs: RunConfigs,
        description: str, download_url: str,
    ) -> tuple[str | None, str]:
        with tempfile.TemporaryDirectory() as tmp:
            raw = os.path.join(tmp, "raw.mp4")
            processed = os.path.join(tmp, "final.mp4")

            if not download_video(download_url, raw):
                return None, "Download thất bại — URL có thể đã hết hạn"

            if not configs.process_video:
                final = raw
            else:
                bg_path = None
                if configs.background:
                    bg_raw = os.path.join(tmp, "bg.mp4")
                    if download_video(configs.background, bg_raw):
                        bg_path = bg_raw

                replace_audio = os.path.join(
                    os.path.dirname(self.settings.db_path), "replace.mp3"
                )
                if configs.replace_audio and not os.path.exists(replace_audio):
                    logger.warning(f"[{page_id}] replaceAudio=true but {replace_audio} not found — skip")
                ok = process_video(
                    raw, processed,
                    ffmpeg_path=self.settings.ffmpeg_path,
                    speed_up=True,
                    resize=True,
                    replace_audio_path=replace_audio if configs.replace_audio else None,
                    background_path=bg_path,
                )
                if not ok:
                    return None, "FFmpeg xử lý thất bại"
                final = processed

            if not validate_video(final, self.settings.ffmpeg_path):
                logger.warning(f"[{page_id}] Video too small, skipping")
                return None, _SKIP

            reel_url = fb.post_reel(page_id, final, description)
            if reel_url:
                return reel_url, ""
            return None, "Facebook API từ chối publish — kiểm tra token và page permissions"


def _build_statistic(page_info: dict, uploaded: int, success: int, failed: int) -> str:
    stat = dict(page_info)
    stat["total_uploaded_video"] = uploaded
    stat["success_uploaded_video"] = success
    stat["fail_uploaded_video"] = failed
    return json.dumps(stat)


def _split_text_and_tags(text: str) -> tuple[str, str]:
    tags = re.findall(r"#\w+", text)
    text_only = re.sub(r"#\w+", "", text).strip()
    return text_only, " ".join(tags)
