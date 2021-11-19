from machine import Pin, Signal, Timer
from random import randrange
import struct

from ktane_lib.constants import CONSTANTS
from log import LOG
from hardware import KtaneHardware

# Constants:
POSTS = (2, 3, 4, 5, 6, 7)
WIRES = (10, 11, 12, 13, 14, 20, 19, 18, 17, 16)

COLOR_POSITIONS = [
    CONSTANTS.COLORS.BLACK,
    CONSTANTS.COLORS.BLACK,
    CONSTANTS.COLORS.BLUE,
    CONSTANTS.COLORS.BLUE,
    CONSTANTS.COLORS.RED,
    CONSTANTS.COLORS.RED,
    CONSTANTS.COLORS.WHITE,
    CONSTANTS.COLORS.WHITE,
    CONSTANTS.COLORS.YELLOW,
    CONSTANTS.COLORS.YELLOW,
]


class WireModule(KtaneHardware):
    right_post: int
    mapping: list
    colors: list

    def __init__(self) -> None:
        KtaneHardware.__init__(self, self.read_config())
        self.handlers.update(
            {
                CONSTANTS.PROTOCOL.PACKET_TYPE.REQUEST_ID: self.request_id,
                CONSTANTS.PROTOCOL.PACKET_TYPE.CONFIGURE: self.configure,
                CONSTANTS.PROTOCOL.PACKET_TYPE.START: self.start,
                CONSTANTS.PROTOCOL.PACKET_TYPE.STOP: self.stop,
                CONSTANTS.PROTOCOL.PACKET_TYPE.DISARMED: self.disarmed,
            }
        )
        self.serial_number = b""
        self.post_pins = [Pin(pin_num, Pin.IN, Pin.PULL_UP) for pin_num in POSTS]
        self.posts = [Signal(pin, invert=True) for pin in self.post_pins]
        self.wires = [Signal(Pin(pin_num, Pin.OUT), invert=True) for pin_num in WIRES]

    @staticmethod
    def read_config() -> int:
        # Format:
        #
        # Field    Length   Notes
        # ------   ------   ---------------------------------------------
        # unique   1        Unique portion of ID, assigned at manufacture
        unique = b""
        try:
            file_obj = open(CONSTANTS.MODULES.CONFIG_FILENAME, "rb")
            unique = file_obj.read(1)
            file_obj.close()
        except OSError:
            pass

        return (CONSTANTS.MODULES.TYPES.WIRES << 8) | (ord(unique) if unique else 0x00)

    def request_id(self, source: int, _dest: int, _payload: bytes) -> bool:
        LOG.debug("request_id")
        Timer(
            mode=Timer.ONE_SHOT,
            period=randrange(*CONSTANTS.PROTOCOL.TIMING.ID_SPREAD_MS),
            callback=lambda timer: self.send_without_queuing(
                source,
                CONSTANTS.PROTOCOL.PACKET_TYPE.RESPONSE_ID,
                struct.pack("BB", CONSTANTS.MODULES.FLAGS.TRIGGER, 0),
            ),
        )
        return True

    def configure(self, _source: int, _dest: int, payload: bytes) -> bool:
        # Payload is the serial number
        self.serial_number = payload
        LOG.debug("configure", payload)
        return False

    def start(self, _source: int, _dest: int, _payload: bytes):
        # Payload is the difficulty but we're not adjustable so we ignore it
        LOG.debug("start")
        if self.serial_number and self.determine_correct_wire():
            self.set_mode(CONSTANTS.MODES.ARMED)
        else:
            self.unable_to_arm()
            self.set_mode(CONSTANTS.MODES.SLEEP)

    def disable_irqs(self):
        # Disable handlers
        for post in self.post_pins:
            post.irq(None)

    def disarmed(self):
        self.disable_irqs()
        KtaneHardware.disarmed(self)

    def stop(self, source: int, dest: int, payload: bytes) -> bool:
        self.disable_irqs()
        return KtaneHardware.stop(self, source, dest, payload)

    def determine_correct_wire(self) -> bool:
        # Map wires-posts
        self.mapping = [None] * len(POSTS)
        for index1 in range(len(WIRES)):
            # Drive one wire
            for index2, wire in enumerate(self.wires):
                wire.value(index1 == index2)

            # Find a driven post
            for index2, post in enumerate(self.posts):
                if post.value():
                    self.mapping[index2] = index1
                    break
        for index2, index1 in enumerate(self.mapping):
            LOG.debug("mapping", index2, index1)

        # Reduce to a list of colors
        self.colors = [COLOR_POSITIONS[mapping] for mapping in self.mapping if mapping is not None]
        for index, color in enumerate(self.colors):
            LOG.debug("colors", index, color)
        num_wires = len(self.colors)

        # Drive the wires
        for wire in self.wires:
            wire.on()

        # Game logic
        last_serial_digit_odd = self.serial_number[-1] in b"13579"
        if num_wires < 3:
            return False
        elif num_wires == 3:
            if CONSTANTS.COLORS.RED not in self.colors:  # No red
                self.should_cut(2)  # Cut second
            elif self.colors[-1] == CONSTANTS.COLORS.WHITE:  # Last is white
                self.should_cut(-1)  # Cut last
            elif self.count_num_of(CONSTANTS.COLORS.BLUE) > 1:  # More than one blue
                self.should_cut(-1, CONSTANTS.COLORS.BLUE)  # Cut last blue
            else:
                self.should_cut(-1)  # Cut last
        elif num_wires == 4:
            # More than one red and last digit of serial number is odd
            if (self.count_num_of(CONSTANTS.COLORS.RED) > 1) and last_serial_digit_odd:
                self.should_cut(-1, CONSTANTS.COLORS.RED)  # Cut last red
            # Last is yellow and no reds
            elif (self.colors[-1] == CONSTANTS.COLORS.YELLOW) and (self.count_num_of(CONSTANTS.COLORS.RED) == 0):
                self.should_cut(1)  # Cut first
            elif self.count_num_of(CONSTANTS.COLORS.BLUE) == 1:  # Exactly one blue
                self.should_cut(1)  # Cut first
            elif self.count_num_of(CONSTANTS.COLORS.YELLOW) > 1:  # More than one yellow
                self.should_cut(-1)  # Cut last
            else:
                self.should_cut(2)  # Cut second
        elif num_wires == 5:
            # Last is black and last digit of serial number is odd
            if (self.colors[-1] == CONSTANTS.COLORS.BLACK) and last_serial_digit_odd:
                self.should_cut(4)  # Cut fourth
            # Exactly one red and more than one yellow
            elif (self.count_num_of(CONSTANTS.COLORS.RED) == 1) and (self.count_num_of(CONSTANTS.COLORS.YELLOW) > 1):
                self.should_cut(1)  # Cut first
            elif self.count_num_of(CONSTANTS.COLORS.BLACK) == 0:  # No black
                self.should_cut(2)  # Cut second
            else:
                self.should_cut(1)  # Cut first
        else:  # if num_wires==6:
            # No yellow and last digit of serial number is odd
            if (self.count_num_of(CONSTANTS.COLORS.YELLOW) == 0) and last_serial_digit_odd:
                self.should_cut(3)  # Cut third
            # Exactly one yellow and more than one white
            elif (self.count_num_of(CONSTANTS.COLORS.YELLOW) == 1) and (self.count_num_of(CONSTANTS.COLORS.WHITE) > 1):
                self.should_cut(4)  # Cut fourth
            elif self.count_num_of(CONSTANTS.COLORS.RED) == 0:  # No red
                self.should_cut(-1)  # Cut last
            else:
                self.should_cut(4)  # Cut fourth
        return True

    def should_cut(self, post_number: int, color=None) -> None:
        LOG.debug("should_cut", post_number, color)

        # Did they specify a color (e.g. "last red" or "first white")?
        if color is None:
            # No all colors, so just skip None
            posts_in_use = [index for index, mapping in enumerate(self.mapping) if mapping is not None]
        else:
            # Specific color
            posts_in_use = [index for index, mapping in enumerate(self.mapping) if COLOR_POSITIONS[mapping] == color]
        if post_number < 0:
            # Count from end
            self.right_post = posts_in_use[post_number]
        else:
            # Post number (Warning: post #1 means index 0!)
            self.right_post = posts_in_use[post_number - 1]

        LOG.info("right_post=", self.right_post)

        for post in self.post_pins:
            post.irq(self.on_wrong_post, trigger=Pin.IRQ_RISING)
        self.post_pins[self.right_post].irq(self.on_right_post, trigger=Pin.IRQ_RISING)

    def count_num_of(self, color_to_count: int) -> int:
        return sum(1 for color in self.colors if color == color_to_count)

    # Called during an interrupt! Don't allocate memory or waste time!
    def pin_fired(self, pin) -> bool:
        for index, post in enumerate(self.post_pins):
            if pin == post:
                if self.mapping[index] is None:
                    return False
                else:
                    self.mapping[index] = None
                    return True
        else:
            return False

    # Called during an interrupt! Don't allocate memory or waste time!
    def on_wrong_post(self, pin):
        if self.pin_fired(pin):
            LOG.info("wrong pin")
            pin.irq(None)
            self.queued |= CONSTANTS.QUEUED_TASKS.STRIKE

    # Called during an interrupt! Don't allocate memory or waste time!
    def on_right_post(self, pin):
        if self.pin_fired(pin):
            LOG.info("right pin")
            pin.irq(None)
            self.queued |= CONSTANTS.QUEUED_TASKS.DISARMED
