
import logging
import os
import sys
import tempfile
import threading
from datetime import datetime, timedelta, timezone

# ==========================================
# DATA CENTER IoT - DAILY COMBINED LOGGER
# ==========================================

IST = timezone(timedelta(hours=5, minutes=30))

VOLUME_LOGS_DIR = "/Volumes/workspace/iot_db/data/dc_logs"
LOCAL_LOGS_DIR = "/tmp/dc_pipeline_logs"

os.makedirs(LOCAL_LOGS_DIR, exist_ok=True)

# Unique local file for each notebook execution
_fd, LOCAL_LOG_FILE = tempfile.mkstemp(
    prefix="dc_pipeline_",
    suffix=".log",
    dir=LOCAL_LOGS_DIR
)
os.close(_fd)

LOG_FORMAT = (
    "%(asctime)s - %(levelname)s - %(name)s - "
    "[%(filename)s:%(lineno)d] - %(message)s"
)

_save_lock = threading.RLock()


# STEP 1: IST time formatter
class ISTFormatter(logging.Formatter):

    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, IST)

        if datefmt:
            return dt.strftime(datefmt)

        return dt.strftime("%Y-%m-%d %H:%M:%S")


# STEP 2: Dedicated pipeline logger
logger = logging.getLogger("pipeline")
logger.setLevel(logging.INFO)
logger.propagate = False

# Remove handlers from previous reloads
for handler in logger.handlers[:]:
    if getattr(handler, "_dc_pipeline_handler", False):
        logger.removeHandler(handler)
        handler.close()


# STEP 3: Local file handler
file_handler = logging.FileHandler(
    LOCAL_LOG_FILE,
    mode="a",
    encoding="utf-8"
)
file_handler._dc_pipeline_handler = True
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(
    ISTFormatter(
        LOG_FORMAT,
        datefmt="%Y-%m-%d %H:%M:%S"
    )
)
logger.addHandler(file_handler)


# STEP 4: Notebook console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler._dc_pipeline_handler = True
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(
    ISTFormatter(
        LOG_FORMAT,
        datefmt="%Y-%m-%d %H:%M:%S"
    )
)
logger.addHandler(console_handler)


# STEP 5: Logger helper
def get_logger(name="pipeline"):
    if name == "pipeline":
        return logger

    return logging.getLogger(f"pipeline.{name}")


# STEP 6: Merge local logs into daily Volume file
def save_logs_to_volume(dbutils=None):

    with _save_lock:

        for handler in logger.handlers:
            handler.flush()

        today = datetime.now(IST).strftime("%Y-%m-%d")

        daily_file = os.path.join(
            VOLUME_LOGS_DIR,
            f"{today}_dc_pipeline.log"
        )

        os.makedirs(VOLUME_LOGS_DIR, exist_ok=True)

        # Read current notebook logs
        with open(
            LOCAL_LOG_FILE,
            "r",
            encoding="utf-8"
        ) as f:
            new_logs = f.read()

        if not new_logs:
            print("No new logs to save")
            return daily_file

        # Read previous daily logs
        previous_logs = ""

        if os.path.exists(daily_file):
            with open(
                daily_file,
                "r",
                encoding="utf-8"
            ) as f:
                previous_logs = f.read()

        # Write merged content to temporary Volume file
        temp_file = daily_file + ".tmp"

        with open(
            temp_file,
            "w",
            encoding="utf-8"
        ) as f:
            f.write(previous_logs)
            f.write(new_logs)

        # Replace daily file
        os.replace(temp_file, daily_file)

        # Clear local log after successful merge
        with open(
            LOCAL_LOG_FILE,
            "w",
            encoding="utf-8"
        ) as f:
            f.write("")

        print("Daily logs saved to:", daily_file)
        print(
            "Daily log file size:",
            os.path.getsize(daily_file),
            "bytes"
        )

        return daily_file
