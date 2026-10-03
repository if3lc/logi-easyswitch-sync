"""Reconnect wake-up and deferred-write behaviour layered on top of 1.5.4.

Background: after an Easy-Switch round trip the gateway sat in an exponential backoff (1, 2, 4 … 30 s)
and only noticed a returning device at the next step — up to 29 s after it was enumerable again. Every
host change written to it in that window was dropped, so the mouse stayed behind.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

from cleverswitch.event.write_event import WriteEvent
from cleverswitch.gateway.hid_gateway import _RECONNECT_BACKOFF_MAX, _RECONNECT_BACKOFF_MIN, HidGateway
from cleverswitch.hidpp.constants import BOLT_PID, REPORT_LONG
from cleverswitch.hidpp.transport import HidDeviceInfo
from cleverswitch.listener.event_listener import EventListener

MSG = bytes([REPORT_LONG]) + bytes(19)


def _device_info(pid=BOLT_PID, usage=0x0002):
    return HidDeviceInfo(
        path=b"/dev/hidraw0", vid=0x046D, pid=pid, usage_page=0xFF00, usage=usage, connection_type="receiver"
    )


def _gateway(connected=False, ever_connected=True) -> HidGateway:
    gw = HidGateway(_device_info(), MagicMock(spec=EventListener))
    gw._transport = MagicMock()
    gw._connected = connected
    gw._ever_connected = ever_connected
    return gw


def _reconnect_and_flush(gw: HidGateway) -> None:
    """Reconnect, then wait for the grace timer so the flush has run (or confirm none was scheduled)."""
    gw._set_connected(True)
    timer = gw._flush_timer
    if timer is not None:
        timer.join(timeout=2.0)
        assert not timer.is_alive(), "flush timer did not fire"


# ── wake() ──────────────────────────────────────────────────────────────────


def test_wake_sets_signal_only_while_disconnected():
    gw = _gateway(connected=True)

    gw.wake()
    assert not gw._wake.is_set()

    gw._connected = False
    gw.wake()
    assert gw._wake.is_set()


def test_wake_interrupts_backoff_without_growing_the_step(mocker):
    gw = _gateway()
    mocker.patch("cleverswitch.gateway.hid_gateway.enumerate_hid_devices", return_value={})
    gw._backoff = 4.0
    gw.wake()

    start = time.monotonic()
    gw._try_connect()

    assert time.monotonic() - start < 1.0, "a woken gateway must not sit out its backoff step"
    assert gw._backoff == 4.0
    assert not gw._wake.is_set(), "the wake signal is consumed by the wait"


def test_backoff_still_grows_when_nothing_wakes_it(mocker):
    gw = _gateway()
    mocker.patch("cleverswitch.gateway.hid_gateway.enumerate_hid_devices", return_value={})
    waits: list[float] = []

    def timed_out(timeout):
        waits.append(timeout)
        return False

    mocker.patch.object(gw._wake, "wait", side_effect=timed_out)

    for _ in range(4):
        gw._try_connect()

    assert waits == [1.0, 2.0, 4.0, _RECONNECT_BACKOFF_MAX]


def test_backoff_cap_is_a_few_seconds():
    """The cap is only a safety net behind wake(); it must never again hide a device for half a minute."""
    assert _RECONNECT_BACKOFF_MAX <= 5.0


def test_successful_connect_clears_stale_wake_and_resets_backoff(mocker):
    info = _device_info()
    gw = HidGateway(info, MagicMock(spec=EventListener))
    gw._backoff = 4.0
    gw._wake.set()
    mocker.patch("cleverswitch.gateway.hid_gateway.enumerate_hid_devices", return_value={info.pid: [info]})
    mocker.patch("cleverswitch.gateway.hid_gateway.HIDTransport")

    gw._try_connect()

    assert gw._connected
    assert not gw._wake.is_set()
    assert gw._backoff == _RECONNECT_BACKOFF_MIN


def test_close_wakes_a_reader_parked_in_backoff():
    gw = _gateway()

    gw.close()

    assert gw._stop.is_set()
    assert gw._wake.is_set()


# ── deferred writes ─────────────────────────────────────────────────────────


def test_write_without_ttl_is_still_dropped_when_disconnected():
    gw = _gateway()

    gw.notify(WriteEvent(slot=1, pid=BOLT_PID, hid_message=MSG))

    assert gw._pending is None
    gw._transport.write.assert_not_called()


def test_write_with_ttl_is_parked_when_disconnected():
    gw = _gateway()

    gw.notify(WriteEvent(slot=1, pid=BOLT_PID, hid_message=MSG, defer_ttl=3.0))

    assert gw._pending is not None
    assert gw._pending[0].hid_message == MSG
    gw._transport.write.assert_not_called()


def test_parked_write_is_sent_after_the_grace_once_reconnected(mocker):
    mocker.patch("cleverswitch.gateway.hid_gateway._DEFERRED_FLUSH_GRACE", 0.05)
    gw = _gateway()
    gw.notify(WriteEvent(slot=1, pid=BOLT_PID, hid_message=MSG, defer_ttl=3.0))

    gw._set_connected(True)
    gw._transport.write.assert_not_called()  # not before the grace
    gw._flush_timer.join(timeout=2.0)

    gw._transport.write.assert_called_once_with(MSG)
    assert gw._pending is None


def test_reconnect_without_parked_write_schedules_nothing():
    gw = _gateway()

    gw._set_connected(True)

    assert gw._flush_timer is None


def test_expired_parked_write_is_discarded_on_reconnect(mocker):
    mocker.patch("cleverswitch.gateway.hid_gateway._DEFERRED_FLUSH_GRACE", 0.0)
    gw = _gateway()
    gw._pending = (WriteEvent(slot=1, pid=BOLT_PID, hid_message=MSG, defer_ttl=3.0), time.monotonic() - 0.1)

    _reconnect_and_flush(gw)

    gw._transport.write.assert_not_called()
    assert gw._pending is None


def test_parked_write_is_discarded_when_its_stale_check_fires(mocker):
    mocker.patch("cleverswitch.gateway.hid_gateway._DEFERRED_FLUSH_GRACE", 0.0)
    gw = _gateway()
    gw.notify(WriteEvent(slot=1, pid=BOLT_PID, hid_message=MSG, defer_ttl=3.0, discard_if=lambda: True))

    _reconnect_and_flush(gw)

    gw._transport.write.assert_not_called()
    assert gw._pending is None


def test_parked_write_is_sent_when_its_stale_check_is_clear(mocker):
    mocker.patch("cleverswitch.gateway.hid_gateway._DEFERRED_FLUSH_GRACE", 0.0)
    gw = _gateway()
    gw.notify(WriteEvent(slot=1, pid=BOLT_PID, hid_message=MSG, defer_ttl=3.0, discard_if=lambda: False))

    _reconnect_and_flush(gw)

    gw._transport.write.assert_called_once_with(MSG)


def test_parked_write_is_kept_if_the_device_drops_again_during_the_grace(mocker):
    mocker.patch("cleverswitch.gateway.hid_gateway._DEFERRED_FLUSH_GRACE", 0.0)
    gw = _gateway()
    gw.notify(WriteEvent(slot=1, pid=BOLT_PID, hid_message=MSG, defer_ttl=3.0))
    gw._connected = True
    gw._connected = False  # dropped again before the flush runs

    gw._flush_pending()

    gw._transport.write.assert_not_called()
    assert gw._pending is not None, "still inside the TTL, so it waits for the next reconnect"


def test_newest_parked_write_supersedes_the_older_one(mocker):
    mocker.patch("cleverswitch.gateway.hid_gateway._DEFERRED_FLUSH_GRACE", 0.0)
    gw = _gateway()
    to_host_1 = bytes([REPORT_LONG, 0xFF, 0x0A, 0x1F, 0x00]) + bytes(15)
    to_host_2 = bytes([REPORT_LONG, 0xFF, 0x0A, 0x1F, 0x01]) + bytes(15)
    gw.notify(WriteEvent(slot=1, pid=BOLT_PID, hid_message=to_host_1, defer_ttl=3.0))
    gw.notify(WriteEvent(slot=1, pid=BOLT_PID, hid_message=to_host_2, defer_ttl=3.0))

    _reconnect_and_flush(gw)

    gw._transport.write.assert_called_once_with(to_host_2)


def test_parked_write_schedules_its_own_flush_when_reconnect_raced_the_park(mocker):
    mocker.patch("cleverswitch.gateway.hid_gateway._DEFERRED_FLUSH_GRACE", 0.0)
    gw = _gateway()
    real_defer = gw._defer

    def connect_then_park(event):
        gw._connected = True  # plain flag flip: the reconnect's own scheduling already ran and found nothing
        real_defer(event)

    mocker.patch.object(gw, "_defer", side_effect=connect_then_park)

    gw.notify(WriteEvent(slot=1, pid=BOLT_PID, hid_message=MSG, defer_ttl=3.0))
    deadline = time.monotonic() + 2.0
    while gw._transport.write.call_count == 0 and time.monotonic() < deadline:
        time.sleep(0.01)

    gw._transport.write.assert_called_once_with(MSG)
    assert gw._pending is None


def test_disconnect_does_not_flush_parked_write():
    gw = _gateway()
    gw.notify(WriteEvent(slot=1, pid=BOLT_PID, hid_message=MSG, defer_ttl=3.0))

    gw._set_connected(False)

    gw._transport.write.assert_not_called()
    assert gw._pending is not None


def test_windows_report_filter_applies_before_parking(mocker):
    """A collection that could never send this report must not park it either."""
    mocker.patch("cleverswitch.gateway.hid_gateway._IS_WINDOWS", True)
    gw = HidGateway(_device_info(usage=0x0001), MagicMock(spec=EventListener))  # short-report collection
    gw._transport = MagicMock()
    gw._connected = False
    gw._ever_connected = True

    gw.notify(WriteEvent(slot=1, pid=BOLT_PID, hid_message=MSG, defer_ttl=3.0))  # long report

    assert gw._pending is None
    gw._transport.write.assert_not_called()
