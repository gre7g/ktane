from machine import Pin, Timer, Signal

from constants import CONSTANTS

# Constants:
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
    workspace = [10, 10, 10, 10]

    def __init__(self, frequency=200):
        self.timer = None
        self.digit = 0
        self.value = self.workspace
        self.decimal_pos = None
        self.colon = False
        self.start(frequency)

    def start(self, frequency):
        if self.timer is None:
            # Enable timer
            self.timer = Timer(freq=frequency, mode=Timer.PERIODIC, callback=self.update)

    def stop(self):
        if self.timer:
            # Clear all 4 segments
            self.display([CONSTANTS.SEVEN_SEGMENT.BLANK] * 4)
            for _ in range(4):
                self.update()

            # Disable timer
            self.timer.deinit()
            self.timer = None

    # Called during an interrupt! Don't allocate memory or waste time!
    def display(self, value, decimal_pos=None, minimum_digits=1, colon=False):
        """Change the display

        :param list|int value: New value to be displayed
        :param int|None decimal_pos: Where to show the decimal (or don't show it, if None)
        :param int minimum_digits: How many digits to show when displaying a number
        """
        if isinstance(value, list):
            self.value = value
        else:
            self.value = self.workspace
            for index in range(4):
                digit = value % 10
                if (value == 0) and (minimum_digits <= index):
                    digit = CONSTANTS.SEVEN_SEGMENT.BLANK
                value = value // 10
                self.value[3 - index] = digit

        self.decimal_pos = decimal_pos
        self.colon = colon

    # Called during an interrupt! Don't allocate memory or waste time!
    def update(self, _timer=None):
        """Update the LEDs"""
        # Turn off previous digit
        DIGITS[self.digit].off()

        # Advance to next digit
        self.digit = (self.digit + 1) % 4

        # Enable segments
        segments = CONSTANTS.SEVEN_SEGMENT.MASK_BY_DIGIT[self.value[self.digit]]
        for segment in range(7):
            SEGMENTS[segment].value(segments & (1 << segment))
        DP.value((self.digit + 1) == self.decimal_pos)

        COLON.value(self.colon and (self.digit % 2))

        # Enable current digit
        DIGITS[self.digit].on()
