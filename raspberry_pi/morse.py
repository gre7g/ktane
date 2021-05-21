from machine import Pin, Signal

from hardware import KtaneHardware, MT_MORSE
from seven_seg import SevenSegment, BLANK, LETTER_R, LETTER_T

# Constants:
CONFIG_FILENAME = "config.txt"
GRAY_DECODE = [2, 1, 3, 0]

FREQUENCIES = [
    3500,
    3505,
    3510,
    3515,
    3520,
    3522,
    3530,
    3532,
    3535,
    3540,
    3543,
    3545,
    3550,
    3552,
    3555,
    3560,
    3565,
    3570,
    3572,
    3575,
    3580,
    3582,
    3590,
    3592,
    3595,
    3600,
]
LAST_FREQ = len(FREQUENCIES) - 1

ROTARY1 = Pin(2, Pin.IN, Pin.PULL_UP)
ROTARY2 = Pin(7, Pin.IN, Pin.PULL_UP)
BUTTON_RX_PIN = Pin(3, Pin.IN, Pin.PULL_UP)
BUTTON_RX = Signal(BUTTON_RX_PIN, invert=True)
BUTTON_TX_PIN = Pin(5, Pin.IN, Pin.PULL_UP)
BUTTON_TX = Signal(BUTTON_TX_PIN, invert=True)

ARRAY_R = [LETTER_R, BLANK, BLANK, BLANK]
ARRAY_T = [BLANK, BLANK, LETTER_T, BLANK]


class MorseModule(KtaneHardware):
    def __init__(self) -> None:
        KtaneHardware.__init__(self, self.read_config())
        self.seven_seg = SevenSegment()
        self.curr_phase = self.phase()
        self.value = 0
        self.offset = 0
        BUTTON_RX_PIN.irq(self.on_rx)
        BUTTON_TX_PIN.irq(self.on_tx)
        ROTARY1.irq(self.on_rotary)
        ROTARY2.irq(self.on_rotary)
        self.display_freq()

    # Called during an interrupt! Don't allocate memory or waste time!
    def on_rx(self, _pin):
        if BUTTON_RX.value():
            self.seven_seg.display(ARRAY_R)
        else:
            self.display_freq()

    # Called during an interrupt! Don't allocate memory or waste time!
    def on_tx(self, _pin):
        if BUTTON_TX.value():
            self.seven_seg.display(ARRAY_T)
        else:
            self.display_freq()

    # Called during an interrupt! Don't allocate memory or waste time!
    def display_freq(self):
        self.seven_seg.display(FREQUENCIES[self.value], 3)

    # Called during an interrupt! Don't allocate memory or waste time!
    @staticmethod
    def phase() -> int:
        return GRAY_DECODE[(2 if ROTARY1.value() else 0) | (1 if ROTARY2.value() else 0)]

    # Called during an interrupt! Don't allocate memory or waste time!
    def on_rotary(self, _pin):
        phase = self.phase()
        direction = (phase - self.curr_phase) & 3
        self.curr_phase = phase
        if direction == 1:
            self.offset += 1
        elif direction == 3:
            self.offset -= 1
        if phase == 0:
            if (self.offset > 0) and (self.value < LAST_FREQ):
                self.value += 1
                self.display_freq()
            elif (self.offset < 0) and (self.value > 0):
                self.value -= 1
                self.display_freq()
            self.offset = 0

    @staticmethod
    def read_config() -> int:
        # Format:
        #
        # Field    Length   Notes
        # ------   ------   ---------------------------------------------
        # unique   1        Unique portion of ID, assigned at manufacture
        unique = b""
        try:
            file_obj = open(CONFIG_FILENAME, "rb")
            unique = file_obj.read(1)
            file_obj.close()
        except OSError:
            pass

        return (MT_MORSE << 8) | (ord(unique) if unique else 0x00)
