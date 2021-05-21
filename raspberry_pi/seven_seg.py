from machine import Pin, Timer, Signal

# Constants:
BLANK = 10
LETTER_R = 11
LETTER_T = 12
MASK_BY_DIGIT = [
    0x7E,  # 0
    0x30,  # 1
    0x6D,  # 2
    0x79,  # 3
    0x33,  # 4
    0x5B,  # 5
    0x5F,  # 6
    0x70,  # 7
    0x7F,  # 8
    0x73,  # 9
    0x00,  # BLANK
    0x05,  # LETTER_R
    0x0F,  # LETTER_T
]

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
        self.start(frequency)

    def start(self, frequency):
        if self.timer is None:
            # Enable timer
            self.timer = Timer(freq=frequency, mode=Timer.PERIODIC, callback=self.update)

    def stop(self):
        if self.timer:
            # Clear all 4 segments
            self.display([BLANK, BLANK, BLANK, BLANK])
            for _ in range(4):
                self.update()

            # Disable timer
            self.timer.deinit()
            self.timer = None

    # Called during an interrupt! Don't allocate memory or waste time!
    def display(self, value, decimal_pos=None, minimum_digits=1):
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
                    digit = BLANK
                value = value // 10
                self.value[3 - index] = digit

        self.decimal_pos = decimal_pos

    # Called during an interrupt! Don't allocate memory or waste time!
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
