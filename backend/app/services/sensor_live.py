"""Bounded, ephemeral live previews for the single-process demo server.

Previews are not inventory evidence and expire when a sensor stops transmitting.
"""
from collections import OrderedDict
from dataclasses import dataclass
from threading import Lock
from time import monotonic


@dataclass(frozen=True)
class LiveFrame:
    inspection_id: int
    jpeg: bytes
    received: float


class LiveFrames:
    def __init__(self) -> None:
        self.frames: OrderedDict[int, LiveFrame] = OrderedDict()
        self.lock = Lock()

    def put(self, sensor_id: int, inspection_id: int, jpeg: bytes) -> None:
        with self.lock:
            self.frames[sensor_id] = LiveFrame(inspection_id, jpeg, monotonic())
            self.frames.move_to_end(sensor_id)
            while len(self.frames) > 32:
                self.frames.popitem(last=False)

    def get(self, sensor_id: int, inspection_id: int) -> bytes | None:
        with self.lock:
            frame = self.frames.get(sensor_id)
            if frame is None:
                return None
            if monotonic() - frame.received > 5:
                self.frames.pop(sensor_id, None)
                return None
            return frame.jpeg if frame.inspection_id == inspection_id else None


@dataclass(frozen=True)
class LiveTelemetry:
    inspection_id: int
    message: str
    detected_code: str | None
    received: float


class LiveTelemetryStore:
    def __init__(self) -> None:
        self.items: dict[int, LiveTelemetry] = {}
        self.lock = Lock()

    def put(self, sensor_id: int, inspection_id: int, message: str, detected_code: str | None) -> None:
        with self.lock:
            self.items[sensor_id] = LiveTelemetry(inspection_id, message, detected_code, monotonic())

    def get(self, sensor_id: int, inspection_id: int) -> LiveTelemetry | None:
        with self.lock:
            item = self.items.get(sensor_id)
            if item is None or monotonic() - item.received > 8 or item.inspection_id != inspection_id:
                return None
            return item

    def clear(self, sensor_id: int, inspection_id: int | None = None) -> None:
        """Forget a candidate after its final evidence is persisted.

        A LOC telemetry event is deliberately ephemeral.  Clearing it avoids a
        stale blue ``SCANNING`` cell masking the newly committed final state
        during the next live-state poll.
        """

        with self.lock:
            item = self.items.get(sensor_id)
            if item is not None and (
                inspection_id is None or item.inspection_id == inspection_id
            ):
                self.items.pop(sensor_id, None)


live_frames = LiveFrames()
live_telemetry = LiveTelemetryStore()
