import os
import sys

from loguru import logger

from src.config.settings import load
from src.worker import ReelsReupWorker

logger.remove()
if os.environ.get("LOG_STDOUT", "true").lower() not in ("false", "0", "no"):
    logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {message}", level="INFO")
logger.add("logs/reup.log", rotation="10 MB", retention="7 days", level="DEBUG")


def main() -> None:
    settings = load()
    worker = ReelsReupWorker(settings)
    worker.run_session()


if __name__ == "__main__":
    main()
