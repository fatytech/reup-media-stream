import requests
from loguru import logger

GRAPH_BASE = "https://graph.facebook.com/v24.0"
RUPLOAD_BASE = "https://rupload.facebook.com/video-upload/v24.0"


class FacebookAPI:
    def __init__(self, access_token: str):
        self.token = access_token
        self._page_info: dict | None = None

    def get_page_info(self) -> dict | None:
        try:
            resp = requests.get(
                f"{GRAPH_BASE}/me",
                params={
                    "access_token": self.token,
                    "fields": "id,name,fan_count,followers_count",
                },
                timeout=15,
            )
            if resp.status_code == 200:
                self._page_info = resp.json()
                return self._page_info
            logger.error(f"get_page_info failed: {resp.text[:200]}")
            return None
        except Exception as e:
            logger.error(f"get_page_info: {e}")
            return None

    def post_reel(self, page_id: str, video_path: str, description: str) -> str | None:
        video_id = self._start_upload(page_id)
        if not video_id:
            return None
        if not self._upload_binary(video_id, video_path):
            return None
        if not self._check_upload_status(video_id):
            return None
        return self._publish(page_id, video_id, description)

    def _start_upload(self, page_id: str) -> str | None:
        try:
            resp = requests.post(
                f"{GRAPH_BASE}/{page_id}/video_reels",
                json={"upload_phase": "start", "access_token": self.token},
                timeout=30,
            )
            data = resp.json()
            if "video_id" not in data:
                logger.error(f"start_upload: {data}")
                return None
            return str(data["video_id"])
        except Exception as e:
            logger.error(f"start_upload: {e}")
            return None

    def _upload_binary(self, video_id: str, video_path: str) -> bool:
        try:
            with open(video_path, "rb") as f:
                video_bytes = f.read()
            resp = requests.post(
                f"{RUPLOAD_BASE}/{video_id}",
                headers={
                    "Authorization": f"OAuth {self.token}",
                    "offset": "0",
                    "file_size": str(len(video_bytes)),
                },
                data=video_bytes,
                timeout=300,
            )
            if resp.status_code not in (200, 204):
                logger.error(f"upload_binary {resp.status_code}: {resp.text[:200]}")
                return False
            data = resp.json()
            if not data.get("success"):
                logger.error(f"upload_binary not success: {data}")
                return False
            return True
        except Exception as e:
            logger.error(f"upload_binary: {e}")
            return False

    def _check_upload_status(self, video_id: str) -> bool:
        try:
            resp = requests.get(
                f"{GRAPH_BASE}/{video_id}",
                params={"fields": "status", "access_token": self.token},
                timeout=30,
            )
            data = resp.json()
            status = data.get("status", {})
            uploading = status.get("uploading_phase", {}).get("status", "")
            has_error = "error" in status.get("processing_phase", {})
            if uploading == "complete" and not has_error:
                return True
            logger.error(f"check_upload_status: uploading={uploading} error={has_error}")
            return False
        except Exception as e:
            logger.error(f"check_upload_status: {e}")
            return False

    def _publish(self, page_id: str, video_id: str, description: str) -> str | None:
        try:
            resp = requests.post(
                f"{GRAPH_BASE}/{page_id}/video_reels",
                params={
                    "access_token": self.token,
                    "video_id": video_id,
                    "upload_phase": "finish",
                    "video_state": "PUBLISHED",
                },
                data={"description": description},
                timeout=30,
            )
            if not resp.ok:
                logger.error(f"publish failed: {resp.text[:200]}")
                return None
            reel_url = f"https://www.facebook.com/reel/{video_id}"
            logger.info(f"Published: {reel_url}")
            return reel_url
        except Exception as e:
            logger.error(f"publish: {e}")
            return None
