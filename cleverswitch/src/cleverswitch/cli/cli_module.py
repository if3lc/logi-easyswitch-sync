"""CLI entry point."""

from __future__ import annotations

import argparse
import logging
import platform
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .. import __version__
from ..cache.device_cache import DeviceCache
from ..config import config as cfg_module
from ..discovery.discovery import discover
from ..errors.errors import CleverSwitchError, ConfigError
from ..hidpp.transport import hidapi_version
from ..setup.app_setup import setup_context

_SYSTEM = platform.system()

_LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"


def main() -> None:
    args = _parse_args()

    _setup_logging(
        args.verbose or args.verbose_extra,
        log_file=args.log_file,
        log_max_mb=args.log_max_mb,
        log_backups=args.log_backups,
    )
    log = logging.getLogger(__name__)

    if args.clear_cache:
        try:
            config = cfg_module.load(args)
        except ConfigError as e:
            log.error(f"{e}")
            sys.exit(1)
        DeviceCache(config.cache_path).clear()
        return

    app_context = setup_context(args)

    try:
        discovery_thread = threading.Thread(
            target=discover,
            args=(app_context,),
        )

        discovery_thread.start()
        discovery_thread.join()
    except CleverSwitchError as e:
        log.error(f"{e}")
        sys.exit(1)

    log.info("CleverSwitch stopped")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="cleverswitch",
        description="Synchronize host switching between Logitech devices",
    )
    p.add_argument("-c", "--config", metavar="FILE", help="path to config YAML file")
    p.add_argument("-v", "--verbose", action="store_true", help="force DEBUG logging")
    p.add_argument("-vv", "--verbose-extra", action="store_true", help="force DEBUG logging including discovery")
    p.add_argument("--clear-cache", action="store_true", help="delete the discovered-device cache and exit")
    p.add_argument("--log-file", metavar="FILE", help="also write the log to FILE, rotated by size")
    p.add_argument(
        "--log-max-mb", type=int, default=10, metavar="N", help="rotate --log-file once it exceeds N MB (default: 10)"
    )
    p.add_argument(
        "--log-backups", type=int, default=5, metavar="N", help="rotated copies of --log-file to keep (default: 5)"
    )
    p.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__} (hidapi {hidapi_version()}, {_SYSTEM})",
    )
    return p.parse_args()


def _setup_logging(verbose: bool, log_file: str | None = None, log_max_mb: int = 10, log_backups: int = 5) -> None:
    if verbose:
        level = "DEBUG"
    else:
        level = "INFO"
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format=_LOG_FORMAT,
        datefmt="%H:%M:%S",
    )
    # Quiet down the hid library's own logger
    logging.getLogger("hid").setLevel(logging.WARNING)
    if log_file:
        _add_rotating_file_handler(log_file, log_max_mb, log_backups)


def _add_rotating_file_handler(log_file: str, max_mb: int, backups: int) -> None:
    """Mirror the log into a size-rotated file so a headless daemon can run with -v/-vv indefinitely."""
    path = Path(log_file).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        path, maxBytes=max(1, max_mb) * 1024 * 1024, backupCount=max(0, backups), encoding="utf-8"
    )
    # Dates matter in a file that spans days; the console format stays as it was.
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt="%Y-%m-%d %H:%M:%S"))
    logging.getLogger().addHandler(handler)
