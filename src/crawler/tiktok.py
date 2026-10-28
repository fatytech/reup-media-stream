from loguru import logger
from src.models.reup_item import ReupItem
import requests

RAPIDAPI_HOST = "tiktok-video-no-watermark2.p.rapidapi.com"


class TiktokCrawler:
    def __init__(self, api_key: str):
        self.headers = {
            "x-rapidapi-key": api_key,
            "x-rapidapi-host": RAPIDAPI_HOST,
        }

    def crawl_user_posts(self, username: str) -> list[ReupItem]:
        items: list[ReupItem] = []
        cursor = 0
        has_more = True

        while has_more:
            try:
                resp = requests.get(
                    f"https://{RAPIDAPI_HOST}/user/posts",
                    params={"unique_id": username, "count": 35, "cursor": cursor},
                    headers=self.headers,
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json().get("data", {})
                posts = data.get("videos", []) or []

                for post in posts:
                    video_id = post.get("video_id", "")
                    if not video_id:  # Slideshow or invalid — skip
                        continue
                    post_url = f"https://www.tiktok.com/@{username}/video/{video_id}"
                    items.append(ReupItem(url=post_url, content=post.get("title", "")))

                has_more = bool(data.get("hasMore", False))
                cursor = int(data.get("cursor", 0))
            except Exception as e:
                logger.error(f"crawl_user_posts @{username}: {e}")
                break

        logger.info(f"Crawled {len(items)} videos from @{username}")
        return items

    def get_direct_url(self, tiktok_url: str) -> str | None:
        try:
            resp = requests.get(
                f"https://{RAPIDAPI_HOST}/",
                params={"url": tiktok_url},
                headers=self.headers,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})
            return data.get("play") or data.get("wmplay")
        except Exception as e:
            logger.error(f"get_direct_url: {e}")
            return None
