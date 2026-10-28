import os
import shutil
import subprocess
import tempfile

import requests
from loguru import logger

MIN_WIDTH = 600
MIN_HEIGHT = 1067
TARGET_WIDTH = 720
TARGET_HEIGHT = 1280


def download_video(url: str, output_path: str) -> bool:
    try:
        resp = requests.get(url, stream=True, timeout=60)
        resp.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        logger.error(f"download_video: {e}")
        return False


def get_video_dimensions(path: str, ffmpeg_path: str = "ffmpeg") -> tuple[int, int]:
    # Replace only the binary name, not any directory components
    parent = os.path.dirname(ffmpeg_path)
    name = os.path.basename(ffmpeg_path).replace("ffmpeg", "ffprobe")
    ffprobe = os.path.join(parent, name) if parent else name
    try:
        result = subprocess.run(
            [ffprobe, "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=15,
        )
        logger.debug(f"ffprobe stdout: {result.stdout.strip()!r} | stderr: {result.stderr[:200]!r}")
        w, h = result.stdout.strip().split(",")
        return int(w), int(h)
    except Exception as e:
        logger.warning(f"get_video_dimensions failed ({ffprobe}): {e}")
        return 0, 0


def validate_video(path: str, ffmpeg_path: str = "ffmpeg") -> bool:
    w, h = get_video_dimensions(path, ffmpeg_path)
    return w >= MIN_WIDTH and h >= MIN_HEIGHT


def process_video(
    input_path: str,
    output_path: str,
    ffmpeg_path: str = "ffmpeg",
    speed_up: bool = True,
    resize: bool = True,
    replace_audio_path: str | None = None,
    background_path: str | None = None,
) -> bool:
    try:
        with tempfile.TemporaryDirectory() as tmp:
            current = input_path

            if speed_up:
                sped = os.path.join(tmp, "sped.mp4")
                _ffmpeg([ffmpeg_path, "-i", current,
                         "-vf", "setpts=0.9*PTS", "-af", "atempo=1.1",
                         "-y", sped])
                current = sped

            if resize:
                resized = os.path.join(tmp, "resized.mp4")
                _ffmpeg([ffmpeg_path, "-i", current,
                         "-vf", (
                             f"scale={TARGET_WIDTH}:{TARGET_HEIGHT}"
                             f":force_original_aspect_ratio=decrease,"
                             f"pad={TARGET_WIDTH}:{TARGET_HEIGHT}:(ow-iw)/2:(oh-ih)/2"
                         ),
                         "-y", resized])
                current = resized

            if background_path and os.path.exists(background_path):
                merged = os.path.join(tmp, "merged.mp4")
                _merge_with_background(current, background_path, merged, ffmpeg_path)
                current = merged

            if replace_audio_path and os.path.exists(replace_audio_path):
                replaced = os.path.join(tmp, "replaced.mp4")
                _ffmpeg([ffmpeg_path,
                         "-i", current, "-i", replace_audio_path,
                         "-map", "0:v", "-map", "1:a", "-shortest",
                         "-y", replaced])
                current = replaced

            shutil.copy2(current, output_path)
            return True
    except Exception as e:
        logger.error(f"process_video: {e}")
        return False


def _merge_with_background(video: str, bg: str, output: str, ffmpeg_path: str) -> None:
    _ffmpeg([
        ffmpeg_path, "-i", bg, "-i", video,
        "-filter_complex",
        (
            f"[0:v]scale={TARGET_WIDTH}:{TARGET_HEIGHT}[bg];"
            f"[1:v]scale={TARGET_WIDTH}:{TARGET_HEIGHT}"
            f":force_original_aspect_ratio=decrease[fg];"
            "[bg][fg]overlay=(W-w)/2:(H-h)/2[v]"
        ),
        "-map", "[v]", "-map", "1:a", "-shortest", "-y", output,
    ])


def _ffmpeg(cmd: list[str]) -> None:
    logger.debug(f"ffmpeg: {' '.join(cmd[1:3])} ...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.stderr:
        logger.debug(f"ffmpeg stderr:\n{result.stderr[-2000:]}")
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed: {result.stderr[-500:]}")
