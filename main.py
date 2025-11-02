#!/usr/bin/env python3
import os
import sys
import subprocess
import datetime
import logging
import argparse
import time
import requests

# ==============================
# 設定（必要なら変更）
# ==============================
ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
LOG_DIR = os.path.join(ROOT_DIR, "logs")
SCRIPTS = [
    "1-csv_downloader_individuals_v01.py",
    "2-csv_downloader_index_v01.py",
    "3-data_processor_v01.py",
    "4-google_sheets_uploader_v02.py",
    "5-momentum_analyzer_v02.py",
    "6-summary_sender_v01.py"
]
# 各スクリプトのタイムアウト（秒）。必要に応じて辞書で個別指定可能。
DEFAULT_TIMEOUT = 600

os.makedirs(LOG_DIR, exist_ok=True)

# ==============================
# ロギング設定（stdout と ファイル）
# ==============================
today_str = datetime.date.today().strftime("%Y%m%d")
log_file_path = os.path.join(LOG_DIR, f"main_log_{today_str}.txt")

logger = logging.getLogger("main")
logger.setLevel(logging.INFO)
fmt = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", "%Y/%m/%d %H:%M:%S")

# stdout handler
sh = logging.StreamHandler(sys.stdout)
sh.setFormatter(fmt)
logger.addHandler(sh)

# file handler (append)
fh = logging.FileHandler(log_file_path, encoding="utf-8")
fh.setFormatter(fmt)
logger.addHandler(fh)

# ==============================
# Discord 通知（オプション）
# ==============================
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK")  # set via GitHub Secrets or env
def notify_discord(msg: str):
    if not DISCORD_WEBHOOK:
        logger.debug("DISCORD_WEBHOOK not set; skipping Discord notification.")
        return
    payload = {"content": msg}
    try:
        resp = requests.post(DISCORD_WEBHOOK, json=payload, timeout=10)
        if resp.status_code // 100 != 2:
            logger.warning(f"Discord webhook returned status {resp.status_code}: {resp.text}")
    except Exception as e:
        logger.exception("Failed to send Discord notification")

# ==============================
# 実行ユーティリティ
# ==============================
def run_script(script_name: str, timeout: int = DEFAULT_TIMEOUT):
    """サブプロセスで外部スクリプト実行。stdout/stderr をログに出す。"""
    script_path = os.path.join(ROOT_DIR, script_name)
    if not os.path.exists(script_path):
        raise FileNotFoundError(f"{script_path} does not exist")

    cmd = [sys.executable, script_path]
    start = datetime.datetime.now()
    logger.info(f"START {script_name}")
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout
        )
        # ログ出力（stdout）
        if proc.stdout:
            for line in proc.stdout.splitlines():
                logger.info(f"[{script_name}] {line}")
        # stderr
        if proc.stderr:
            for line in proc.stderr.splitlines():
                logger.error(f"[{script_name}][ERR] {line}")

        if proc.returncode != 0:
            raise subprocess.CalledProcessError(proc.returncode, cmd, output=proc.stdout, stderr=proc.stderr)

        elapsed = (datetime.datetime.now() - start).total_seconds()
        logger.info(f"END {script_name} (elapsed {elapsed:.1f}s)")
        return True
    except subprocess.TimeoutExpired as e:
        logger.exception(f"Timeout executing {script_name} (>{timeout}s)")
        return False
    except subprocess.CalledProcessError as e:
        logger.exception(f"Script {script_name} failed with returncode {e.returncode}")
        return False
    except Exception as e:
        logger.exception(f"Unexpected error running {script_name}: {e}")
        return False

# ==============================
# メイン処理
# ==============================
def main(continue_on_error=False):
    overall_ok = True
    for script in SCRIPTS:
        ok = run_script(script)
        if not ok:
            overall_ok = False
            if not continue_on_error:
                logger.error(f"Aborting because {script} failed and continue_on_error=False")
                break
            else:
                logger.warning(f"Continue despite {script} failure (continue_on_error=True)")

    if overall_ok:
        notify_discord(f"✅ Momentum run succeeded: {datetime.datetime.now().isoformat()}")
        logger.info("All scripts completed successfully.")
        return 0
    else:
        notify_discord(f"❌ Momentum run FAILED: {datetime.datetime.now().isoformat()}")
        logger.error("One or more scripts failed. Check logs.")
        return 2

# ==============================
# CLI / CI-friendly 起動
# ==============================
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Run once and exit (useful for CI).")
    parser.add_argument("--continue-on-error", action="store_true", help="Continue running remaining scripts even if one fails.")
    args = parser.parse_args()

    # GitHub Actions 等のCI環境では単回実行（常駐不要）
    if os.environ.get("GITHUB_ACTIONS") or args.once:
        exit_code = main(continue_on_error=args.continue_on_error)
        sys.exit(exit_code)

    # ローカルで常駐させたい場合は、簡単なループ（Ctrl+Cで終了）
    try:
        import schedule
        logger.info("Starting local scheduler (daily at 17:00). Use Ctrl+C to stop.")
        schedule.every().day.at("17:00").do(lambda: main(continue_on_error=args.continue_on_error))
        while True:
            schedule.run_pending()
            time.sleep(30)
    except KeyboardInterrupt:
        logger.info("Interrupted by user. Exiting.")
        sys.exit(0)