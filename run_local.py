"""
Local scheduler — chạy reup session mỗi INTERVAL giờ.
Usage: python run_local.py [--interval <hours>]
"""
import subprocess
import sys
import time
import argparse
from datetime import datetime, timedelta


def parse_args() -> int:
    parser = argparse.ArgumentParser(description="Local scheduler cho reels_tiktok_reup")
    parser.add_argument("--interval", type=float, default=3.0, metavar="HOURS",
                        help="Khoảng cách giữa mỗi lần chạy (giờ). Mặc định: 3")
    return parser.parse_args().interval


def run_session() -> bool:
    print(f"\n{'='*60}")
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Bắt đầu session...")
    print(f"{'='*60}")
    result = subprocess.run([sys.executable, "-m", "src.main"])
    ok = result.returncode == 0
    status = "OK" if ok else f"FAILED (exit {result.returncode})"
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Session kết thúc: {status}")
    return ok


def main() -> None:
    interval_hours = parse_args()
    interval_secs = int(interval_hours * 3600)

    print(f"Local scheduler khởi động — interval: {interval_hours}h")
    print("Nhấn Ctrl+C để dừng.\n")

    while True:
        run_session()
        next_run = datetime.now() + timedelta(seconds=interval_secs)
        print(f"Lần chạy tiếp theo: {next_run:%Y-%m-%d %H:%M:%S}")
        try:
            time.sleep(interval_secs)
        except KeyboardInterrupt:
            print("\nDừng scheduler.")
            sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nDừng scheduler.")
        sys.exit(0)
