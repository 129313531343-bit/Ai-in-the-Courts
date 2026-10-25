"""Wait until a Message Batch has ended, then print its request counts.

Usage: python scripts/wait_batch.py <batch_id> [poll_seconds]
"""

import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    import anthropic

    load_dotenv(ROOT / ".env")
    batch_id = sys.argv[1]
    poll = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    client = anthropic.Anthropic()
    while True:
        b = client.messages.batches.retrieve(batch_id)
        if b.processing_status == "ended":
            c = b.request_counts
            print(f"{batch_id} ended: succeeded {c.succeeded}, errored {c.errored}, "
                  f"canceled {c.canceled}, expired {c.expired}", flush=True)
            return
        time.sleep(poll)


if __name__ == "__main__":
    main()
