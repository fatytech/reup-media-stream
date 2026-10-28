import requests
from dataclasses import dataclass
from loguru import logger

from src.models.run_configs import RunConfigs

COL_LAST_SESSION = 4
COL_STATUS = 5
COL_STATISTIC = 6


@dataclass
class RowItem:
    row: int
    vps: str
    token: str
    tiktok_channels: list[str]
    status: str
    run_configs: RunConfigs
    statistic: str = ""


class AppScriptLoader:
    def __init__(self, appscript_url: str, sheet_id: str, sheet_name: str):
        self._base = appscript_url.rstrip("?") + "?"
        self._sheet_id = sheet_id
        self._sheet_name = sheet_name

    def _read_url(self) -> str:
        return f"{self._base}sheetName={self._sheet_name}&sheetID={self._sheet_id}&operation=read"

    def _write_url(self, row: int, column: int, value: str) -> str:
        return (
            f"{self._base}sheetName={self._sheet_name}&sheetID={self._sheet_id}"
            f"&row={row}&column={column}&operation=write&cellValue={value}"
        )

    def fetch_row_items(self) -> list[RowItem]:
        try:
            resp = requests.get(self._read_url(), timeout=30)
            resp.raise_for_status()
            items = []
            for obj in resp.json():
                try:
                    tiktok_raw = obj.get("tiktok", "")
                    channels = [c.strip() for c in tiktok_raw.split(",") if c.strip()]
                    run_configs = RunConfigs.from_json(obj.get("run_configs", ""))
                    items.append(RowItem(
                        row=int(obj["row"]),
                        vps=obj.get("vps", ""),
                        token=obj.get("token", ""),
                        tiktok_channels=channels,
                        status=obj.get("status", ""),
                        run_configs=run_configs,
                        statistic=obj.get("statistic", ""),
                    ))
                except Exception as e:
                    logger.warning(f"Skip malformed row: {e}")
            return items
        except Exception as e:
            logger.error(f"fetch_row_items failed: {e}")
            return []

    def update_last_session(self, item: RowItem) -> None:
        from datetime import datetime
        value = datetime.now().strftime("%d-%m-%Y %H-%M-%S")
        try:
            requests.get(self._write_url(item.row, COL_LAST_SESSION, value), timeout=30)
        except Exception as e:
            logger.error(f"update_last_session failed: {e}")

    def update_status(self, item: RowItem, status: str) -> None:
        try:
            requests.get(self._write_url(item.row, COL_STATUS, status), timeout=30)
        except Exception as e:
            logger.error(f"update_status failed: {e}")

    def update_statistic(self, item: RowItem) -> None:
        try:
            requests.get(self._write_url(item.row, COL_STATISTIC, item.statistic), timeout=30)
        except Exception as e:
            logger.error(f"update_statistic failed: {e}")
