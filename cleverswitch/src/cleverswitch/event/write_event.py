import dataclasses
from collections.abc import Callable

from ..event.event import Event


@dataclasses.dataclass
class WriteEvent(Event):
    hid_message: bytes
    # Seconds this write may wait for a disconnected gateway to reconnect before it is discarded.
    # 0 (the default) keeps the original behaviour: a write to a disconnected device is dropped.
    defer_ttl: float = 0.0
    # Consulted right before a deferred write is finally sent; True means it has gone stale and
    # must be discarded instead (e.g. the user has already switched back to this host).
    discard_if: Callable[[], bool] | None = dataclasses.field(default=None, compare=False, repr=False)
