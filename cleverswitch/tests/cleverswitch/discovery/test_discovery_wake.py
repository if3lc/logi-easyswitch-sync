"""The discovery sweep wakes gateways whose pid is enumerable again."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock

from cleverswitch.discovery.discovery import discover
from cleverswitch.hidpp.transport import HidDeviceInfo
from cleverswitch.model.context.app_context import AppContext
from cleverswitch.registry.logi_device_registry import LogiDeviceRegistry
from cleverswitch.topic.topic import Topic
from cleverswitch.topic.topics import Topics


def _make_app_context(shutdown):
    topics = Topics(
        hid_event=MagicMock(spec=Topic),
        write=MagicMock(spec=Topic),
        device_info=MagicMock(spec=Topic),
        flags=MagicMock(spec=Topic),
        info_progress=MagicMock(spec=Topic),
    )
    config = MagicMock()
    config.arguments_settings.verbose_extra = False
    return AppContext(device_registry=LogiDeviceRegistry(), topics=topics, config=config, shutdown=shutdown)


def _bt_mouse():
    return HidDeviceInfo(
        path=b"/dev/hidraw1", vid=0x046D, pid=0xB023, usage_page=0xFF43, usage=0x0202, connection_type="bluetooth"
    )


def _run_sweeps(mocker, enumerations: list[dict], gateway) -> None:
    """Run discover() once per entry of *enumerations*, then shut down."""
    enum = mocker.patch("cleverswitch.discovery.discovery.enumerate_hid_devices", side_effect=enumerations)
    mocker.patch("cleverswitch.discovery.discovery.HidGatewayBT", return_value=gateway)
    mocker.patch("cleverswitch.discovery.discovery.EventListener")
    mocker.patch("cleverswitch.discovery.discovery.get_system", return_value="Windows")

    shutdown = threading.Event()

    def fake_wait(timeout):
        if enum.call_count >= len(enumerations):
            shutdown.set()

    shutdown.wait = fake_wait
    discover(_make_app_context(shutdown))


def test_known_pid_in_a_later_sweep_wakes_its_gateway_instead_of_creating_another(mocker):
    gateway = mocker.MagicMock()
    device = _bt_mouse()

    _run_sweeps(mocker, [{0xB023: [device]}, {0xB023: [device]}], gateway)

    assert gateway.start.call_count == 1
    gateway.wake.assert_called_once()


def test_absent_pid_does_not_wake_its_gateway(mocker):
    gateway = mocker.MagicMock()
    device = _bt_mouse()

    _run_sweeps(mocker, [{0xB023: [device]}, {}], gateway)

    gateway.wake.assert_not_called()
