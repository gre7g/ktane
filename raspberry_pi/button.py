from machine import Pin, Signal, Timer, disable_irq, enable_irq
from random import choice, randrange
import struct

from constants import CONSTANTS
from hardware import KtaneHardware
from log import LOG

# Constants:
DEBOUNCE_MS = 100
STRIP_COLORS = [
    CONSTANTS.COLORS.BLUE,
    CONSTANTS.COLORS.WHITE,
    CONSTANTS.COLORS.YELLOW,
    CONSTANTS.COLORS.RED,
    CONSTANTS.COLORS.GREEN,
]
LED_MAP = {
    CONSTANTS.COLORS.BLACK: 0x0,
    CONSTANTS.COLORS.BLUE: 0x1,
    CONSTANTS.COLORS.WHITE: 0x7,
    CONSTANTS.COLORS.YELLOW: 0x6,
    CONSTANTS.COLORS.RED: 0x4,
    CONSTANTS.COLORS.GREEN: 0x2,
}
RED_LEDS = [Signal(Pin(pin_num, Pin.OUT), invert=True) for pin_num in (21, 14, 13, 18)]
GREEN_LEDS = [Signal(Pin(pin_num, Pin.OUT), invert=True) for pin_num in (22, 16, 12, 19)]
BLUE_LEDS = [Signal(Pin(pin_num, Pin.OUT), invert=True) for pin_num in (26, 17, 11, 20)]
BUTTON_PIN = Pin(2, Pin.IN, Pin.PULL_UP)
BUTTON = Signal(BUTTON_PIN, invert=True)


class ButtonModule(KtaneHardware):
    def __init__(self) -> None:
        KtaneHardware.__init__(self, self.read_config())
        self.handlers.update(
            {
                CONSTANTS.PROTOCOL.PACKET_TYPE.REQUEST_ID: self.request_id,
                CONSTANTS.PROTOCOL.PACKET_TYPE.CONFIGURE: self.configure,
                CONSTANTS.PROTOCOL.PACKET_TYPE.START: self.start,
                CONSTANTS.PROTOCOL.PACKET_TYPE.STOP: self.stop,
                CONSTANTS.PROTOCOL.PACKET_TYPE.DISARMED: self.disarmed,
                CONSTANTS.PROTOCOL.PACKET_TYPE.STATUS: self.status,
            }
        )
        self.debouncing = False
        self.button_color = None
        self.button_text = b""
        self.num_batteries = 0
        self.indicator_lit = False
        self.indicator_label = b""
        self.strip_color = None
        self.button_pushed = False
        BUTTON_PIN.irq(self.on_button)
        self.set_strip(LED_MAP[CONSTANTS.COLORS.BLACK])

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

        return (CONSTANTS.MODULES.TYPES.BUTTON << 8) | (ord(unique) if unique else 0x00)

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
        # Payload:
        #
        # Field            Length   Notes
        # --------------   ------   -----------------------------------------
        # color            1        From CONSTANTS.COLORS
        # button_text      8        Text right-padded with \x00's
        # num_batteries    1        Number of batteries visible
        # indicator_lit    1        True if indicator is lit, False otherwise
        # indicator_label  3        Label text
        (
            self.button_color,
            self.button_text,
            self.num_batteries,
            indicator_lit,
            self.indicator_label,
        ) = struct.unpack("<B8sBB3s", payload)
        self.indicator_lit = bool(indicator_lit)
        LOG.debug("configure", payload)
        return False

    def start(self, _source: int, _dest: int, _payload: bytes) -> bool:
        # Payload is the difficulty but we're not adjustable so we ignore it
        LOG.debug("start")
        if self.button_color is not None:
            self.strip_color = choice(STRIP_COLORS)
            self.set_mode(CONSTANTS.MODES.ARMED)
        else:
            self.unable_to_arm()
            self.set_mode(CONSTANTS.MODES.SLEEP)
        return False

    # Called during an interrupt! Don't allocate memory or waste time!
    def on_debounce(self, _timer):
        self.debouncing = False

        # Just in case they've released it already...
        self.on_button()

    # Called during an interrupt! Don't allocate memory or waste time!
    def on_button(self, _pin=None):
        if not self.debouncing:
            button = BUTTON.value()
            if self.button_pushed != button:
                self.debouncing = True
                Timer(period=DEBOUNCE_MS, mode=Timer.ONE_SHOT, callback=self.on_debounce)
                self.button_pushed = button
                if button:
                    self.pushed()
                else:
                    self.released()

    # Called during an interrupt! Don't allocate memory or waste time!
    def set_strip(self, rgb: int):
        for index in range(4):
            RED_LEDS[index].value(rgb & 0x4)
            GREEN_LEDS[index].value(rgb & 0x2)
            BLUE_LEDS[index].value(rgb & 0x1)

    # Called during an interrupt! Don't allocate memory or waste time!
    def pushed(self):
        LOG.info("pushed")
        self.set_strip(LED_MAP[self.strip_color])

    # Called during an interrupt! Don't allocate memory or waste time!
    def released(self):
        LOG.info("released")
        self.set_strip(LED_MAP[CONSTANTS.COLORS.BLACK])
        self.queued |= CONSTANTS.QUEUED_TASKS.READ_STATUS

    def status(self, _source: int, _dest: int, payload: bytes = b"") -> bool:
        # Payload:
        #
        # Field     Length   Notes
        # -------   ------   -----------------------------------------
        # running   1        True is the game is in play
        # strikes   1        Number of strikes
        # time      5        Time as a string, like " 1:12" or "16.92"
        LOG.debug("status", payload)
        _running, _strikes, time = struct.unpack("<BB5s", payload)

        # Game logic
        if (self.button_color == CONSTANTS.COLORS.BLUE) and (self.button_text == CONSTANTS.LABELS.ABORT):
            self.check_time(time)
        elif (self.num_batteries > 1) and (self.button_text == CONSTANTS.LABELS.DETONATE):
            self.disarmed()
        elif (
            (self.button_color == CONSTANTS.COLORS.WHITE)
            and self.indicator_lit
            and (self.indicator_label == CONSTANTS.LABELS.CAR)
        ):
            self.check_time(time)
        elif (self.num_batteries > 2) and self.indicator_lit and (self.indicator_label == CONSTANTS.LABELS.FKR):
            self.disarmed()
        elif self.button_color == CONSTANTS.COLORS.YELLOW:
            self.check_time(time)
        elif (self.button_color == CONSTANTS.COLORS.RED) and (self.button_text == CONSTANTS.LABELS.HOLD):
            self.disarmed()
        else:
            self.check_time(time)

        return True  # The status message is essentiall an ACK, so no additional ACK is required

    def check_time(self, time: bytes):
        if self.strip_color == CONSTANTS.COLORS.BLUE:
            match = b"4" in time
        elif self.strip_color == CONSTANTS.COLORS.WHITE:
            match = b"1" in time
        elif self.strip_color == CONSTANTS.COLORS.YELLOW:
            match = b"5" in time
        else:
            match = b"1" in time

        state = disable_irq()
        if match:
            self.queued |= CONSTANTS.QUEUED_TASKS.DISARMED
        else:
            self.queued |= CONSTANTS.QUEUED_TASKS.STRIKE
        enable_irq(state)
