"""HostChangeSubscriber parks host changes for peers that are not open yet — never for the source."""

from __future__ import annotations

from unittest.mock import MagicMock

from cleverswitch.event.host_change_event import HostChangeEvent
from cleverswitch.event.write_event import WriteEvent
from cleverswitch.hidpp.constants import BOLT_PID, FEATURE_CHANGE_HOST
from cleverswitch.model.logi_device import LogiDevice
from cleverswitch.registry.logi_device_registry import LogiDeviceRegistry
from cleverswitch.subscriber.host_change_subscriber import HOST_CHANGE_DEFER_TTL, HostChangeSubscriber
from cleverswitch.topic.topic import Topic
from cleverswitch.topic.topics import Topics


def _make_topics():
    return Topics(
        hid_event=MagicMock(spec=Topic),
        write=MagicMock(spec=Topic),
        device_info=MagicMock(spec=Topic),
        flags=MagicMock(spec=Topic),
        info_progress=MagicMock(spec=Topic),
    )


def _device(wpid, pid, slot, role):
    return LogiDevice(wpid=wpid, pid=pid, slot=slot, role=role, available_features={FEATURE_CHANGE_HOST: 9}, name=role)


def _published(topics) -> list[WriteEvent]:
    return [call.args[0] for call in topics.write.publish.call_args_list]


def test_receiver_devices_share_a_pid_so_the_source_is_told_apart_by_slot():
    registry = LogiDeviceRegistry()
    topics = _make_topics()
    HostChangeSubscriber(registry, topics)
    registry.register(0x407B, _device(0x407B, BOLT_PID, slot=1, role="keyboard"))
    registry.register(0x4082, _device(0x4082, BOLT_PID, slot=2, role="mouse"))

    topics.hid_event.subscribe.call_args.args[0].notify(HostChangeEvent(slot=1, pid=BOLT_PID, target_host=0))

    by_slot = {event.slot: event for event in _published(topics)}
    assert by_slot[1].defer_ttl == 0.0, "the keyboard that reported the press is already leaving"
    assert by_slot[1].discard_if is None
    assert by_slot[2].defer_ttl == HOST_CHANGE_DEFER_TTL
    assert by_slot[2].discard_if is not None


def test_bluetooth_devices_share_a_slot_so_the_source_is_told_apart_by_pid():
    registry = LogiDeviceRegistry()
    topics = _make_topics()
    HostChangeSubscriber(registry, topics)
    registry.register(0xB35B, _device(0xB35B, 0xB35B, slot=0xFF, role="keyboard"))
    registry.register(0xB023, _device(0xB023, 0xB023, slot=0xFF, role="mouse"))

    topics.hid_event.subscribe.call_args.args[0].notify(HostChangeEvent(slot=0xFF, pid=0xB35B, target_host=0))

    by_pid = {event.pid: event for event in _published(topics)}
    assert by_pid[0xB35B].defer_ttl == 0.0
    assert by_pid[0xB023].defer_ttl == HOST_CHANGE_DEFER_TTL


def test_parked_host_change_turns_stale_once_the_source_keyboard_is_back():
    registry = LogiDeviceRegistry()
    topics = _make_topics()
    HostChangeSubscriber(registry, topics)
    keyboard = _device(0xB35B, 0xB35B, slot=0xFF, role="keyboard")
    registry.register(0xB35B, keyboard)
    registry.register(0xB023, _device(0xB023, 0xB023, slot=0xFF, role="mouse"))

    topics.hid_event.subscribe.call_args.args[0].notify(HostChangeEvent(slot=0xFF, pid=0xB35B, target_host=0))

    mouse_write = {event.pid: event for event in _published(topics)}[0xB023]
    keyboard.connected = False  # it left for the other host, as it does right after the press
    assert mouse_write.discard_if() is False
    keyboard.connected = True  # the user pressed the other host's key and it came back
    assert mouse_write.discard_if() is True


def test_unknown_source_yields_no_stale_check():
    registry = LogiDeviceRegistry()
    topics = _make_topics()
    HostChangeSubscriber(registry, topics)
    registry.register(0xB023, _device(0xB023, 0xB023, slot=0xFF, role="mouse"))

    topics.hid_event.subscribe.call_args.args[0].notify(HostChangeEvent(slot=0xFF, pid=0xB35B, target_host=0))

    (mouse_write,) = _published(topics)
    assert mouse_write.defer_ttl == HOST_CHANGE_DEFER_TTL
    assert mouse_write.discard_if is None


def test_defer_ttl_is_bounded():
    assert 0 < HOST_CHANGE_DEFER_TTL <= 15.0
