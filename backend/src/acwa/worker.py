import argparse
import logging
import os
import socket
import time

from acwa.clock import SystemClock
from acwa.config import get_settings
from acwa.db import get_session_factory
from acwa.logging_config import setup_logging
from acwa.main import build_generator, build_threads
from acwa.security.crypto import TokenCipher
from acwa.services.worker import run_once

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Account Warm-up background worker")
    parser.add_argument("--once", action="store_true", help="Process at most one job and exit")
    args = parser.parse_args()
    settings = get_settings()
    setup_logging(settings.log_level)
    factory = get_session_factory()
    clock = SystemClock()
    cipher = TokenCipher(settings.token_encryption_key)
    generator = build_generator(settings)
    threads = build_threads(settings)
    worker_id = f"{socket.gethostname()}-{os.getpid()}"
    while True:
        session = factory()
        try:
            worked = run_once(
                session,
                settings=settings,
                clock=clock,
                generator=generator,
                threads=threads,
                cipher=cipher,
                worker_id=worker_id,
            )
        except Exception:
            session.rollback()
            logger.exception("worker loop error")
            worked = False
        finally:
            session.close()
        if args.once:
            return
        if not worked:
            time.sleep(settings.worker_poll_seconds)


if __name__ == "__main__":
    main()
