from machine import Pin, lightsleep

from hardware import KtaneHardware, MT_MORSE

# Constants:
CONFIG_FILENAME = "config.txt"
GRAY_DECODE = [2, 1, 3, 0]

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
BUTTON_RX = Pin(3, Pin.IN, Pin.PULL_UP)
BUTTON_TX = Pin(5, Pin.IN, Pin.PULL_UP)
SEG_D1 = Pin(18, Pin.OUT)
SEG_D1.on()
SEG_D2 = Pin(16, Pin.OUT)
SEG_D2.on()
SEG_D3 = Pin(22, Pin.OUT)
SEG_D3.on()
SEG_D4 = Pin(17, Pin.OUT)
SEG_D4.on()
SEG_A = Pin(14, Pin.OUT)
SEG_B = Pin(12, Pin.OUT)
SEG_C = Pin(20, Pin.OUT)
SEG_D = Pin(10, Pin.OUT)
SEG_E = Pin(11, Pin.OUT)
SEG_F = Pin(19, Pin.OUT)
SEG_G = Pin(13, Pin.OUT)
DP = Pin(4, Pin.OUT)
COLON = Pin(6, Pin.OUT)
COLON.on()
L3 = Pin(21, Pin.OUT)
L3.on()
DIGITS = [SEG_D1, SEG_D2, SEG_D3, SEG_D4]


class MorseModule(KtaneHardware):
    def __init__(self) -> None:
        KtaneHardware.__init__(self, self.read_config())
        for pin in SEG_D1, SEG_D2, SEG_D3, SEG_D4, SEG_A, SEG_B, SEG_C, SEG_D, SEG_E, SEG_F, SEG_G, DP, COLON, L3:
            pin.on()
        self.curr_phase = self.phase()
        self.value = 0
        self.offset = 0
        self.decimals = 3

    def poll(self) -> None:
        # Is the knob turning?
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
            elif (self.offset < 0) and (self.value > 0):
                self.value -= 1
            self.offset = 0

        # What should we display?
        if not BUTTON_RX.value():
            value = "r   "
            decimal_pos = None
        elif not BUTTON_TX.value():
            value = "  t "
            decimal_pos = None
        else:
            value = FREQUENCIES[self.value]
            decimal_pos = 3 - self.decimals

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

        # Display
        for index, pin in enumerate(DIGITS):
            digit = MASK_BY_DIGIT[value[index]]
            for segment in SEG_A, SEG_B, SEG_C, SEG_D, SEG_E, SEG_F, SEG_G, DP:
                segment.on()
            pin.off()
            if digit & 0x40:
                SEG_A.off()
            if digit & 0x20:
                SEG_B.off()
            if digit & 0x10:
                SEG_C.off()
            if digit & 0x08:
                SEG_D.off()
            if digit & 0x04:
                SEG_E.off()
            if digit & 0x02:
                SEG_F.off()
            if digit & 0x01:
                SEG_G.off()
            DP.value(index != decimal_pos)
            KtaneHardware.poll(self)
            lightsleep(1)
            pin.on()

    @staticmethod
    def phase() -> int:
        return GRAY_DECODE[(2 if ROTARY1.value() else 0) | (1 if ROTARY2.value() else 0)]

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
