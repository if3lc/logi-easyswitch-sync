"""--log-file: size-rotated log mirror for the headless daemon."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from cleverswitch.cli.cli_module import _parse_args, _setup_logging


def test_parse_args_log_file_defaults(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["cleverswitch"])
    args = _parse_args()
    assert args.log_file is None
    assert args.log_max_mb == 10
    assert args.log_backups == 5


def test_parse_args_log_file_options(monkeypatch):
    monkeypatch.setattr(
        sys, "argv", ["cleverswitch", "--log-file", "cs.log", "--log-max-mb", "2", "--log-backups", "1"]
    )
    args = _parse_args()
    assert args.log_file == "cs.log"
    assert args.log_max_mb == 2
    assert args.log_backups == 1


def test_setup_logging_without_log_file_adds_no_handler(mocker):
    mocker.patch("cleverswitch.cli.cli_module.logging.basicConfig")
    root = logging.getLogger()
    before = list(root.handlers)

    _setup_logging(verbose=True)

    assert root.handlers == before


def test_setup_logging_adds_rotating_file_handler_and_creates_parent_dir(tmp_path, mocker):
    mocker.patch("cleverswitch.cli.cli_module.logging.basicConfig")
    root = logging.getLogger()
    before = list(root.handlers)
    log_path = tmp_path / "logs" / "cleverswitch.log"

    _setup_logging(verbose=True, log_file=str(log_path), log_max_mb=1, log_backups=2)

    added = [handler for handler in root.handlers if handler not in before]
    try:
        assert len(added) == 1
        handler = added[0]
        assert isinstance(handler, RotatingFileHandler)
        assert handler.maxBytes == 1024 * 1024
        assert handler.backupCount == 2
        assert log_path.parent.is_dir()
    finally:
        for handler in added:
            root.removeHandler(handler)
            handler.close()
