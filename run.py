"""Development server entry point.

On Windows + Python 3.14, psycopg async requires SelectorEventLoop
(not the default ProactorEventLoop).  We create the loop explicitly
and run uvicorn on it so the policy cannot be overridden.
"""

from __future__ import annotations

import asyncio
import sys

import uvicorn

# Suppress the DeprecationWarning about WindowsSelectorEventLoopPolicy.
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning, module="asyncio")


def main() -> None:
    if sys.platform == "win32":
        loop = asyncio.SelectorEventLoop()
        asyncio.set_event_loop(loop)
    else:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    config = uvicorn.Config(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        loop="asyncio",
    )
    server = uvicorn.Server(config)

    try:
        loop.run_until_complete(server.serve())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()


if __name__ == "__main__":
    main()