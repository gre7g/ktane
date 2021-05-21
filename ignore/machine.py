class Pin:
    IN = PULL_UP = OUT = IRQ_RISING = None

    def __init__(self, *args, **kwargs):
        pass

    def init(self, *args, **kwargs):
        pass

    def irq(self, handler, trigger=None):
        pass

    def value(self, new_value=None):
        pass

    def off(self):
        pass

    def on(self):
        pass


class Signal:
    def __init__(self, pin, invert=False):
        pass

    def value(self, new_value=None):
        pass

    def off(self):
        pass

    def on(self):
        pass


class Timer:
    PERIODIC = ONE_SHOT = None

    def init(self, freq=None, period=None, mode=None, callback=None):
        pass
