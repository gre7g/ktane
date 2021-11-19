try:
    from timer import TimerModule
    TimerModule().poll_forever()
except ImportError:
    pass

try:
    from wires import WireModule
    WireModule().poll_forever()
except ImportError:
    pass

try:
    from button import ButtonModule
    ButtonModule().poll_forever()
except ImportError:
    pass
