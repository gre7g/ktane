from machine import Pin, Timer, Signal

# Cosntants:
MASK_BY_DIGIT = {
    "0": 0x7E,
    "1": 0x30,
    "2": 0x6D,
    "3": 0x79,
    "4": 0x33,
    "5": 0x5B,
    "6": 0x5F,
    "7": 0x70,
    "8": 0x7F,
    "9": 0x73,
    " ": 0x00,
    "r": 0x05,
    "t": 0x0F,
}

SEGMENTS = [Signal(Pin(pin, Pin.OUT), invert=True) for pin in [13, 19, 11, 10, 20, 12, 14]]
DIGITS = [Signal(Pin(pin, Pin.OUT), invert=True) for pin in [18, 16, 22, 17]]
for digit in DIGITS:
    digit.off()
DP = Signal(Pin(4, Pin.OUT), invert=True)
COLON = Signal(Pin(6, Pin.OUT), invert=True)
COLON.off()
L3 = Signal(Pin(21, Pin.OUT), invert=True)
L3.off()


class SevenSegment:
    def __init__(self, frequency=200):
        self.timer = None
        self.digit = 0
        self.value = "    "
        self.decimal_pos = None
        self.start(frequency)

    def start(self, frequency):
        if self.timer is None:
            # Enable timer
            self.timer = Timer()
            self.timer.init(freq=frequency, mode=Timer.PERIODIC, callback=self.update)

    def stop(self):
        if self.timer:
            # Clear all 4 segments
            self.display("    ")
            for _ in range(4):
                self.update()

            # Disable timer
            self.timer.deinit()
            self.timer = None

    def display(self, value, decimal_pos=None):
        """Change the display

        :param str|int value: New value to be displayed
        :param int|None decimal_pos: Where to show the decimal (or don't show it, if None)
        """
        # Convert numeric display to string
        if isinstance(value, int):
            value = str(value)
            if decimal_pos is not None:
                more_zeroes = 4 - len(value) - decimal_pos
                if more_zeroes > 0:
                    value = ("0" * more_zeroes) + value
            more_spaces = 4 - len(value)
            if more_spaces > 0:
                value = (" " * more_spaces) + value

        self.decimal_pos = decimal_pos
        self.value = value

    def update(self, _timer=None):
        """Update the LEDs"""
        # Turn off previous digit
        DIGITS[self.digit].off()

        # Advance to next digit
        self.digit = (self.digit + 1) % 4

        # Enable segments
        segments = MASK_BY_DIGIT[self.value[self.digit]]
        for segment in range(7):
            SEGMENTS[segment].value(segments & (1 << segment))
        DP.value(self.digit == self.decimal_pos)

        # Enable current digit
        DIGITS[self.digit].on()
