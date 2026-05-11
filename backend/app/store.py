from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque

from .models import Alert, Device, SensorReading


@dataclass
class MemoryStore:
    devices: dict[str, Device] = field(default_factory=dict)
    readings: Deque[SensorReading] = field(default_factory=lambda: deque(maxlen=2000))
    alerts: Deque[Alert] = field(default_factory=lambda: deque(maxlen=500))

    def clear(self) -> None:
        self.devices.clear()
        self.readings.clear()
        self.alerts.clear()


store = MemoryStore()

