from machine import Timer
from utime import ticks_us

from hardware import KtaneHardware
from log import LOG
from seven_seg import SevenSegment

# Constants:
SWITCH_TO_HUNDREDTHS = 60000000  # 60s


class TimerModule(KtaneHardware):
    def __init__(self) -> None:
        KtaneHardware.__init__(self, 0)
        self.seven_seg = None
        self.hundredths_mode = False
        self.timer = None
        self.stop_time = 0

    def start_timer(self, time: int):
        if not self.timer:
            self.hundredths_mode = time < SWITCH_TO_HUNDREDTHS
            LOG.info("100ths", self.hundredths_mode)
            self.timer = Timer(mode=Timer.PERIODIC, freq=100 if self.hundredths_mode else 1, callback=self.on_timer)
            self.stop_time = ticks_us() + time
            self.seven_seg = SevenSegment()
            self.on_timer()

    def stop_timer(self):
        if self.seven_seg:
            self.seven_seg.stop()
            self.seven_seg = None
        if self.timer:
            self.timer.deinit()
            self.timer = None

    # Called during an interrupt! Don't allocate memory or waste time!
    def on_timer(self, timer=None):
        remaining = self.stop_time - ticks_us()
        hundredths_mode = remaining < SWITCH_TO_HUNDREDTHS

        if remaining < 0:
            self.seven_seg.display(0, 2, 3)
            self.timer.deinit()
            self.timer = None
            LOG.info("timer zero")
        else:
            if hundredths_mode:
                number = remaining // 10000
                self.seven_seg.display(number, 2, 3)
            else:
                number = remaining // 1000000
                self.seven_seg.display(((number // 60) * 100) + (number % 60), minimum_digits=3, colon=True)

            if hundredths_mode and not self.hundredths_mode:
                # Switch to hundredths mode
                self.hundredths_mode = True
                self.timer.deinit()
                self.timer = Timer(mode=Timer.PERIODIC, freq=100, callback=self.on_timer)
                LOG.info("switch to 100ths")
