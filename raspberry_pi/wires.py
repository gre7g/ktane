from machine import Pin
import struct

from hardware import (
    KtaneHardware,
    MODE_ARMED,
    PT_REQUEST_ID,
    MT_WIRES,
    PT_RESPONSE_ID,
    FLAG_TRIGGER,
    PT_CONFIGURE,
    PT_START,
    LOG,
    MODE_SLEEP,
)

# Constants:
CONFIG_FILENAME = "config.txt"
POSTS = (2, 3, 4, 5, 6, 7)
WIRES = (10, 11, 12, 13, 14, 20, 19, 18, 17, 16)

BLACK = 0
BLUE = 1
RED = 2
WHITE = 3
YELLOW = 4

COLOR_POSITIONS = [BLACK, BLACK, BLUE, BLUE, RED, RED, WHITE, WHITE, YELLOW, YELLOW]


class WireModule(KtaneHardware):
    should_cut: int

    def __init__(self) -> None:
        KtaneHardware.__init__(self, self.read_config())
        self.handlers.update({PT_REQUEST_ID: self.request_id, PT_CONFIGURE: self.configure, PT_START: self.start})
        self.serial_number = b""
        self.posts = [Pin(pin_num, Pin.IN, Pin.PULL_UP) for pin_num in POSTS]
        self.wires = [Pin(pin_num, Pin.OUT) for pin_num in WIRES]

        # Map them
        self.mapping = [None] * len(POSTS)
        for index1 in range(len(WIRES)):
            for index2, wire in enumerate(self.wires):
                wire.value(index1 != index2)
            for index2, post in enumerate(self.posts):
                if not post.value():
                    self.mapping[index2] = index1
                    break

        self.colors = [COLOR_POSITIONS[mapping] for mapping in self.mapping if mapping is not None]

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

        return (MT_WIRES << 8) | (ord(unique) if unique else 0x00)

    def request_id(self, source: int, _dest: int, _payload: bytes) -> bool:
        LOG("request_id")
        self.send_without_queuing(source, PT_RESPONSE_ID, struct.pack("BB", FLAG_TRIGGER, 0))
        return True

    def configure(self, _source: int, _dest: int, payload: bytes) -> bool:
        # Payload is the serial number
        self.serial_number = payload
        LOG("configure", payload)
        return False

    def start(self, _source: int, _dest: int, _payload: bytes) -> bool:
        # Payload is the difficulty but we're not adjustable so we ignore it
        LOG("start")
        if self.serial_number and self.determine_correct_wire():
            self.set_mode(MODE_ARMED)
        else:
            self.unable_to_arm()
            self.set_mode(MODE_SLEEP)
        return False

    def determine_correct_wire(self) -> bool:
        num_wires = len(self.colors)
        last_serial_digit_odd = self.serial_number[-1] in b"13579"
        if num_wires < 3:
            return False
        elif num_wires == 3:
            if RED not in self.colors:  # No red
                self.should_cut(2)  # Cut second
            elif self.colors[-1] == WHITE:  # Last is white
                self.should_cut(-1)  # Cut last
            elif self.count_num_of(BLUE) > 1:  # More than one blue
                self.should_cut(-1, BLUE)  # Cut last blue
            else:
                self.should_cut(-1)  # Cut last
        elif num_wires == 4:
            # More than one red and last digit of serial number is odd
            if (self.count_num_of(RED) > 1) and last_serial_digit_odd:
                self.should_cut(-1, RED)  # Cut last red
            # Last is yellow and no reds
            elif (self.colors[-1] == YELLOW) and (self.count_num_of(RED) == 0):
                self.should_cut(1)  # Cut first
            elif self.count_num_of(BLUE) == 1:  # Exactly one blue
                self.should_cut(1)  # Cut first
            elif self.count_num_of(YELLOW) > 1:  # More than one yellow
                self.should_cut(-1)  # Cut last
            else:
                self.should_cut(2)  # Cut second
        elif num_wires == 5:
            # Last is black and last digit of serial number is odd
            if (self.colors[-1] == BLACK) and last_serial_digit_odd:
                self.should_cut(4)  # Cut fourth
            # Exactly one red and more than one yellow
            elif (self.count_num_of(RED) == 1) and (self.count_num_of(YELLOW) > 1):
                self.should_cut(1)  # Cut first
            elif self.count_num_of(BLACK) == 0:  # No black
                self.should_cut(2)  # Cut second
            else:
                self.should_cut(1)  # Cut first
        else:  # if num_wires==6:
            # No yellow and last digit of serial number is odd
            if (self.count_num_of(YELLOW) == 0) and last_serial_digit_odd:
                self.should_cut(3)  # Cut third
            # Exactly one yellow and more than one white
            elif (self.count_num_of(YELLOW) == 1) and (self.count_num_of(WHITE) > 1):
                self.should_cut(4)  # Cut fourth
            elif self.count_num_of(RED) == 0:  # No red
                self.should_cut(-1)  # Cut last
            else:
                self.should_cut(4)  # Cut fourth
        return True

    def should_cut(self, wire_number: int, color=None) -> None:
        # Did they specify a color (e.g. "last red" or "first white")?
        if color is None:
            # No all colors, so just skip None
            mapping_skip_nones = [mapping for mapping in self.mapping if mapping is not None]
        else:
            # Specific color
            mapping_skip_nones = [mapping for mapping in self.mapping if mapping == color]
        if wire_number < 0:
            # Count from end
            self.should_cut = mapping_skip_nones[wire_number]
        else:
            # Wire number (Warning: wire #1 means index 0!)
            self.should_cut = mapping_skip_nones[wire_number - 1]

        LOG("should_cut=", self.should_cut)

    def count_num_of(self, color_to_count: int) -> int:
        return len(1 for color in self.colors if color == color_to_count)

    def poll(self) -> None:
        KtaneHardware.poll(self)

        # When the module is running, check if a wire has been cut
        if self.mode == MODE_ARMED:
            for index, mapping in enumerate(self.mapping):
                if (mapping is not None) and self.wires[mapping].value():
                    # Wire cut! Was it the right one?
                    if mapping == self.should_cut:
                        self.disarmed()
                    else:
                        self.strike()

                        # Remove the wire from the mapping so we don't poll it again
                        self.mapping[index] = None
