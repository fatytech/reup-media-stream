import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@dataclass
class Settings:
    vps_id: str
    ffmpeg_path: str
    rapidapi_key: str
    db_path: str
    appscript_url: str
    sheet_id: str
    sheet_name: str
    telegram_token: str
    telegram_chat_id: str
    ai_api_key: str


def load() -> Settings:
    return Settings(
        vps_id=os.environ.get("VPS_ID", "github-actions"),
        ffmpeg_path=os.environ.get("FFMPEG_PATH", "ffmpeg"),
        rapidapi_key=os.environ["RAPIDAPI_KEY"],
        db_path=os.environ.get("DB_PATH", "data/reel_tiktok_reup.db"),
        appscript_url=os.environ["APPSCRIPT_URL"],
        sheet_id=os.environ["SHEET_ID"],
        sheet_name=os.environ.get("SHEET_NAME", "reel_tiktok_reup"),
        telegram_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id=os.environ.get("TELEGRAM_CHAT_ID", ""),
        ai_api_key=os.environ.get("AI_API_KEY", ""),
    )
