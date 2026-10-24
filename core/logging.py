import logging


def setup_logging(level: int = logging.INFO) -> None:
    """Make application loggers visible when running under uvicorn.

    Celery configures the root logger itself in workers; only add a handler if
    none exists, so this never duplicates output.
    """
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    else:
        root.setLevel(min(root.level or level, level))
