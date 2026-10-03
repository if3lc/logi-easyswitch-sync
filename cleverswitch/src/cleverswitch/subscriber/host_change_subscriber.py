import logging

from ..event.host_change_event import HostChangeEvent
from ..event.write_event import WriteEvent
from ..hidpp.constants import (
    CHANGE_HOST_FN_SET,
    FEATURE_CHANGE_HOST,
    SW_ID_HOST_CHANGE,
)
from ..hidpp.protocol import build_msg, pack_params
from ..registry.logi_device_registry import LogiDeviceRegistry
from ..subscriber.subscriber import Subscriber
from ..topic.topics import Topics

log = logging.getLogger(__name__)

# An Easy-Switch press often lands while the peer device is still re-linking to this host (it
# trails the keyboard by 1–6 s in the logs), or while a sleeping mouse has dropped its link. A host
# change for a peer that is not open is parked for this long and sent once its gateway reconnects —
# unless the source keyboard is back on this host by then, which means the user has already
# switched back and the parked command would only bounce the peer away again.
HOST_CHANGE_DEFER_TTL = 10.0


class HostChangeSubscriber(Subscriber):
    def __init__(self, device_registry: LogiDeviceRegistry, topics: Topics):
        self._device_registry = device_registry
        self._topics = topics
        topics.hid_event.subscribe(self)

    def notify(self, event) -> None:
        if not isinstance(event, HostChangeEvent):
            return

        devices = self._device_registry.all_entries()
        source = next((d for d in devices if d.pid == event.pid and d.slot == event.slot), None)

        for device in devices:
            change_host_idx = device.available_features.get(FEATURE_CHANGE_HOST)
            if change_host_idx is None:
                continue

            request_id = (change_host_idx << 8) | (CHANGE_HOST_FN_SET & 0xF0) | SW_ID_HOST_CHANGE
            params = pack_params((event.target_host,))
            msg = build_msg(device.slot, request_id, params)
            if device is source:
                # The device that reported the press switches natively and is already leaving —
                # never park a write for it, or a quick return trip would be bounced straight back.
                write = WriteEvent(slot=device.slot, pid=device.pid, hid_message=msg)
            else:
                write = WriteEvent(
                    slot=device.slot,
                    pid=device.pid,
                    hid_message=msg,
                    defer_ttl=HOST_CHANGE_DEFER_TTL,
                    discard_if=_source_is_back(source),
                )
            self._topics.write.publish(write)
            log.info(f"Sending host change to '{device.display_name}' -> host {event.target_host + 1}")


def _source_is_back(source):
    """Stale check for a parked host change: the keyboard that asked for it is connected here again."""
    if source is None:
        return None
    return lambda: source.connected
