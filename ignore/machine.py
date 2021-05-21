class Pin:
    IN = PULL_UP = None

    def __init__(self, *args, **kwargs):
        pass

    def irq(self, handler):
        pass

    def value(self, new_value=None):
        pass


class Signal:
    def __init__(self, pin, invert=False):
        pass

    def value(self, new_value=None):
        pass


class Timer:
    pass
