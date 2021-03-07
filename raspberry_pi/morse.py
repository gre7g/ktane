from machine import Pin, lightsleep

from hardware import KtaneHardware, MT_MORSE

# Constants:
CONFIG_FILENAME = "config.txt"
GRAY_DECODE = [2, 1, 3, 0]

MASK_BY_DIGIT = {
    "0": 0x01,
    "1": 0x4F,
    "2": 0x12,
    "3": 0x06,
    "4": 0x4C,
    "5": 0x24,
    "6": 0x20,
    "7": 0x0F,
    "8": 0x00,
    "9": 0x0C,
    " ": 0x7F,
    "r": 0x7A,
    "t": 0x70,
}

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
DIGITS = [SEG_D1, SEG_D2, SEG_D3, SEG_D4]


class MorseModule(KtaneHardware):
    def __init__(self) -> None:
        KtaneHardware.__init__(self, self.read_config())
        for pin in SEG_D1, SEG_D2, SEG_D3, SEG_D4, SEG_A, SEG_B, SEG_C, SEG_D, SEG_E, SEG_F, SEG_G:
            pin.on()
        self.curr_phase = self.phase()
        self.value = 500
        self.offset = 0
        self.decimals = 2

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
            if (self.offset > 0) and (self.value < 9990):
                self.value += 10
            elif (self.offset < 0) and (self.value > 0):
                self.value -= 10
            self.offset = 0

        # What should we display?
        if not BUTTON_RX.value():
            value = "r   "
        elif not BUTTON_TX.value():
            value = "  t "
        else:
            value = self.value

        # Convert numeric display to string
        if isinstance(value, int):
            value = str(value)
            more_zeroes = self.decimals - len(value) + 1
            if more_zeroes > 0:
                value = ("0" * more_zeroes) + value
            more_spaces = 4 - len(value)
            if more_spaces > 0:
                value = (" " * more_spaces) + value

        # Display
        for index, pin in enumerate(DIGITS):
            digit = MASK_BY_DIGIT[value[index]]
            pin.off()
            SEG_A.value(digit & 0x40)
            SEG_B.value(digit & 0x20)
            SEG_C.value(digit & 0x10)
            SEG_D.value(digit & 0x08)
            SEG_E.value(digit & 0x04)
            SEG_F.value(digit & 0x02)
            SEG_G.value(digit & 0x01)
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
