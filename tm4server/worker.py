from __future__ import annotations
import time

from .config import POLL_INTERVAL_S
from .runner import init_dirs, process_one


def main() -> None:
    init_dirs()
    print(f"TM4 Worker started (polling every {POLL_INTERVAL_S}s)")
    try:
        while True:
            processed = process_one()
            if not processed:
                time.sleep(POLL_INTERVAL_S)
    except KeyboardInterrupt:
        print("Worker stopped.")


if __name__ == "__main__":
    main()
