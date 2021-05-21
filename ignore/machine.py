from typing import Optional, Callable


class Pin:
    IN = PULL_UP = OUT = IRQ_RISING = None

    def __init__(self, *args, **kwargs):
        pass

    def init(self, *args, **kwargs):
        pass

    def irq(self, handler: Optional[Callable], trigger=None):
        pass

    def value(self, new_value: Optional[bool] = None) -> bool:
        pass

    def off(self):
        pass

    def on(self):
        pass


class Signal:
    def __init__(self, pin, invert=False):
        pass

    def value(self, new_value=None) -> bool:
        pass

    def off(self):
        pass

    def on(self):
        pass


class Timer:
    PERIODIC = ONE_SHOT = None

    def __init__(
        self, freq: Optional[int] = None, period: Optional[int] = None, mode=None, callback: Optional[Callable] = None
    ):
        pass

    def init(
        self, freq: Optional[int] = None, period: Optional[int] = None, mode=None, callback: Optional[Callable] = None
    ):
        pass


class UART:
    def __init__(
        self,
        uart_id,
        baudrate: int = 9600,
        bits: int = 8,
        parity=None,
        stop: int = 1,
        tx: Optional[Pin] = None,
        rx: Optional[Pin] = None,
        timeout: Optional[int] = None,
        timeout_char: Optional[int] = None,
    ):
        pass

    def any(self) -> int:
        pass

    def read(self, count: int) -> Optional[bytes]:
        pass

    def write(self, buffer: bytes) -> Optional[int]:
        pass

    def sendbreak(self):
        pass
