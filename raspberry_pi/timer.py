from machine import Timer
from random import randrange
import struct
from utime import ticks_us

from ktane_lib.constants import CONSTANTS
from hardware import KtaneHardware
from log import LOG
from seven_seg import SevenSegment

# Constants:
SWITCH_TO_HUNDREDTHS = 60000000  # 60s

MODE_READY = 0
MODE_PAUSE = 1
MODE_RUNNING = 2
MODE_SHOW_ERROR = 3
MODE_STRIKE = 4
MODE_LOSE = 5

ARRAY_BLANK = [
    CONSTANTS.SEVEN_SEGMENT.BLANK,
    CONSTANTS.SEVEN_SEGMENT.BLANK,
    CONSTANTS.SEVEN_SEGMENT.BLANK,
    CONSTANTS.SEVEN_SEGMENT.BLANK,
]
ARRAY_ERR = [
    CONSTANTS.SEVEN_SEGMENT.LETTER_E,
    CONSTANTS.SEVEN_SEGMENT.LETTER_R,
    CONSTANTS.SEVEN_SEGMENT.LETTER_R,
    CONSTANTS.SEVEN_SEGMENT.BLANK,
]
ARRAY_STRIKE_1 = [
    CONSTANTS.SEVEN_SEGMENT.LETTER_S,
    CONSTANTS.SEVEN_SEGMENT.BLANK,
    1,
    CONSTANTS.SEVEN_SEGMENT.BLANK,
]
ARRAY_STRIKE_2 = [
    CONSTANTS.SEVEN_SEGMENT.LETTER_S,
    CONSTANTS.SEVEN_SEGMENT.BLANK,
    2,
    CONSTANTS.SEVEN_SEGMENT.BLANK,
]
ARRAY_LOSE = [
    CONSTANTS.SEVEN_SEGMENT.LETTER_L,
    CONSTANTS.SEVEN_SEGMENT.LETTER_O,
    CONSTANTS.SEVEN_SEGMENT.LETTER_S,
    CONSTANTS.SEVEN_SEGMENT.LETTER_E,
]


class TimerModule(KtaneHardware):
    def __init__(self) -> None:
        KtaneHardware.__init__(self, self.read_config())
        self.handlers.update(
            {
                CONSTANTS.PROTOCOL.PACKET_TYPE.REQUEST_ID: self.request_id,
                CONSTANTS.PROTOCOL.PACKET_TYPE.SET_TIME: self.set_time,
                CONSTANTS.PROTOCOL.PACKET_TYPE.SHOW_TIME: self.show_time,
                CONSTANTS.PROTOCOL.PACKET_TYPE.START: self.start,
                CONSTANTS.PROTOCOL.PACKET_TYPE.STOP: self.stop,
            }
        )
        self.display_mode = MODE_READY
        self.seven_seg = None
        self.hundredths_mode = False
        self.timer = None
        self.stop_time = 0
        self.change_mode_time = 0
        self.strikes = 0
        self.display(MODE_READY)

    #     self.state=0
    #     self.fsm(CONSTANTS.FSM_REASON.POWER_UP)
    #
    # def fsm(self, reason):
    #     if reason==CONSTANTS.FSM_REASON.POWER_UP:
    #         Timer(mode=Timer.ONE_SHOT,period=CONSTANTS.MODULES.TIMER.START_UP_MS,callback=lambda timer:self.fsm(CONSTANTS.FSM_REASON.TIMER))
    #         self.state=CONSTANTS.STATES.START
    #     elif (self.state==CONSTANTS.STATES.START)and(reason==CONSTANTS.FSM_REASON.TIMER):
    #         self.send_without_queuing(CONSTANTS.MODULES.BROADCAST_ALL,CONSTANTS.PROTOCOL.PACKET_TYPE.REQUEST_ID)
    #         self.state=CONSTANTS.STATES.

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

        return (CONSTANTS.MODULES.TYPES.TIMER << 8) | (ord(unique) if unique else 0x00)

    def request_id(self, source: int, _dest: int, _payload: bytes) -> bool:
        LOG.debug("request_id")
        Timer(
            mode=Timer.ONE_SHOT,
            period=randrange(*CONSTANTS.PROTOCOL.TIMING.ID_SPREAD_MS),
            callback=lambda timer: self.send_without_queuing(
                source,
                CONSTANTS.PROTOCOL.PACKET_TYPE.RESPONSE_ID,
                struct.pack("BB", CONSTANTS.MODULES.FLAGS.EXCLUSIVE, 0),
            ),
        )
        return True  # I handled my own ACK

    def set_time(self, source: int, _dest: int, _payload: bytes):
        LOG.debug("set_time")
        (time_left,) = struct.unpack("<L", _payload)
        self.start_timer(time_left)

    def show_time(self, source: int, _dest: int, _payload: bytes):
        LOG.debug("show_time")
        (time_left,) = struct.unpack("<L", _payload)
        self.display_mode = MODE_PAUSE
        if self.timer:
            self.timer.deinit()
            self.timer = None
        if not self.seven_seg:
            self.seven_seg = SevenSegment()
        self.show_remaining(time_left, time_left < SWITCH_TO_HUNDREDTHS)

    def start(self, _source: int = 0, _dest: int = 0, _payload: bytes = b""):
        # Payload is the difficulty but we're not adjustable so we ignore it
        LOG.debug("start")

    def stop(self, source: int, dest: int, payload: bytes) -> bool:
        self.stop_timer()
        return KtaneHardware.stop(self, source, dest, payload)

    def start_timer(self, time: int):
        self.stop_time = ticks_us() + time
        self.hundredths_mode = time < SWITCH_TO_HUNDREDTHS
        self.display(MODE_RUNNING)
        LOG.debug("100ths", self.hundredths_mode)

    def stop_timer(self):
        if self.seven_seg:
            self.seven_seg.stop()
            self.seven_seg = None
        if self.timer:
            self.timer.deinit()
            self.timer = None

    # Called during an interrupt! Don't allocate memory or waste time!
    def display(self, mode: int):
        self.display_mode = mode
        if self.timer:
            self.timer.deinit()
            self.timer = None
        if mode == MODE_READY:
            self.timer = Timer(
                mode=Timer.PERIODIC, freq=int(1000000 / CONSTANTS.MODULES.TIMER.READY_DUTY), callback=self.on_timer
            )
        elif mode == MODE_RUNNING:
            self.timer = Timer(mode=Timer.PERIODIC, freq=100 if self.hundredths_mode else 1, callback=self.on_timer)
            self.on_timer()
        elif mode == MODE_SHOW_ERROR:
            self.seven_seg.display(ARRAY_ERR)
            self.timer = Timer(mode=Timer.ONE_SHOT, period=CONSTANTS.MODULES.TIMER.ALERT_MS, callback=self.on_timer)
        elif mode == MODE_LOSE:
            self.seven_seg.display(ARRAY_LOSE)
            self.timer = Timer(mode=Timer.ONE_SHOT, period=CONSTANTS.MODULES.TIMER.ALERT_MS, callback=self.on_timer)
        else:  # if mode==MODE_STRIKE:
            self.seven_seg.display(ARRAY_STRIKE_1 if self.strikes == 1 else ARRAY_STRIKE_2)
            self.timer = Timer(mode=Timer.ONE_SHOT, period=CONSTANTS.MODULES.TIMER.STRIKE_MS, callback=self.on_timer)

    # Called during an interrupt! Don't allocate memory or waste time!
    def on_timer(self, timer=None):
        if self.seven_seg:
            # Which mode are we in?
            if self.display_mode == MODE_READY:
                # Flash
                flash = (ticks_us() % CONSTANTS.MODULES.TIMER.READY_BLINK) < CONSTANTS.MODULES.TIMER.READY_DUTY
                self.seven_seg.display(ARRAY_BLANK, colon=flash)
            elif self.display_mode == MODE_RUNNING:
                self.update_countdown()
            elif self.display_mode == MODE_STRIKE:
                self.display(MODE_READY if self.mode == CONSTANTS.MODES.ENDED else MODE_RUNNING)
            else:  # if (self.display_mode == MODE_SHOW_ERROR) or (self.display_mode == MODE_LOSE):
                self.display(MODE_READY)

    def update_countdown(self):
        remaining = self.stop_time - ticks_us()
        hundredths_mode = remaining < SWITCH_TO_HUNDREDTHS

        if (remaining > 0) and (hundredths_mode and not self.hundredths_mode):
            # Switch to hundredths mode
            self.hundredths_mode = True
            self.timer.deinit()
            self.timer = Timer(mode=Timer.PERIODIC, freq=100, callback=self.on_timer)
            LOG.info("switch to 100ths")

        self.show_remaining(remaining, hundredths_mode)

    def show_remaining(self, remaining, hundredths_mode):
        if remaining < 0:
            self.display(MODE_LOSE)
            LOG.info("timer zero")
        else:
            if hundredths_mode:
                number = remaining // 10000
                self.seven_seg.display(number, 2, 3)
            else:
                number = remaining // 1000000
                self.seven_seg.display(((number // 60) * 100) + (number % 60), minimum_digits=3, colon=True)
