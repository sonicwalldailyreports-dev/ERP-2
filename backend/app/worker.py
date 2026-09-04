"""Production worker entrypoint for durable database-backed jobs."""

import asyncio
import logging

from app.core.config import get_settings
from app.core.jobs import BackgroundWorker, default_handlers
from app.db.session import create_engine, create_session_factory


async def main() -> None:
    settings = get_settings()
    engine = create_engine(settings)
    sessions = create_session_factory(engine)
    worker = BackgroundWorker(settings, default_handlers(settings=settings))
    try:
        while True:
            async with sessions() as session:
                await worker.run_until_empty(session)
            await asyncio.sleep(2)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=get_settings().log_level)
    asyncio.run(main())
