from ktane_lib.constants import CONSTANTS
from machine import Pin, UART, Signal, disable_irq, enable_irq, idle
from utime import ticks_us

from log import LOG
from ktane_lib.ktane_base import KtaneBase, QueuedPacket

# Constants:
UART_NUM = 1
TX_PIN = 8
RX_PIN = 9
TX_EN_PIN = 15

STATUS_RED = 28
STATUS_GREEN = 27


class KtaneHardware(KtaneBase):
    mode: int

    def __init__(self, addr: int) -> None:
        uart = UART(UART_NUM, CONSTANTS.UART.BAUD_RATE, tx=Pin(TX_PIN), rx=Pin(RX_PIN))
        tx_en = Pin(TX_EN_PIN, Pin.OUT)
        KtaneBase.__init__(self, addr, uart, tx_en, LOG, idle, ticks_us)
        self.status_red = Signal(Pin(STATUS_RED, Pin.OUT), invert=True)
        self.status_green = Signal(Pin(STATUS_GREEN, Pin.OUT), invert=True)
        self.set_mode(CONSTANTS.MODES.SLEEP)

    def set_mode(self, mode: int) -> None:
        self.mode = mode
        if mode == CONSTANTS.MODES.SLEEP:
            LOG.info("mode=sleep")
            self.status_green.off()
            self.status_red.off()
        elif mode in [CONSTANTS.MODES.ARMED, CONSTANTS.MODES.READY]:
            LOG.info("mode=armed or ready")
            self.status_green.off()
            self.status_red.on()
        elif mode == CONSTANTS.MODES.DISARMED:
            LOG.info("mode=disarmed")
            self.status_green.on()
            self.status_red.off()

    def check_queued_tasks(self, was_idle):
        if self.queued & CONSTANTS.QUEUED_TASKS.STRIKE:
            was_idle = False
            self.strike()
            state = disable_irq()
            self.queued &= ~CONSTANTS.QUEUED_TASKS.STRIKE
            enable_irq(state)

        if self.queued & CONSTANTS.QUEUED_TASKS.DISARMED:
            was_idle = False
            self.disarmed()
            state = disable_irq()
            self.queued &= ~CONSTANTS.QUEUED_TASKS.DISARMED
            enable_irq(state)

        if self.queued & CONSTANTS.QUEUED_TASKS.READ_STATUS:
            self.LOG.debug("read status")
            was_idle = False
            seq_num = (self.last_seq_seen + 1) & 0xFF
            self.last_seq_seen = seq_num
            self.queue_packet(QueuedPacket(CONSTANTS.MODULES.TIMER_ADDR << 8, CONSTANTS.PROTOCOL.PACKET_TYPE.READ_STATUS, seq_num))
            state = disable_irq()
            self.queued &= ~CONSTANTS.QUEUED_TASKS.READ_STATUS
            enable_irq(state)

        if was_idle:
            self.idle()

    def unable_to_arm(self) -> None:
        LOG.info("error")
        self.queue_packet(QueuedPacket(CONSTANTS.MODULES.TIMER_ADDR, CONSTANTS.PROTOCOL.PACKET_TYPE.ERROR))

    def disarmed(self):
        LOG.info("disarmed")
        self.queue_packet(QueuedPacket(CONSTANTS.MODULES.TIMER_ADDR, CONSTANTS.PROTOCOL.PACKET_TYPE.DISARMED))
        self.set_mode(CONSTANTS.MODES.DISARMED)

    def strike(self):
        LOG.info("strike")
        self.queue_packet(QueuedPacket(CONSTANTS.MODULES.TIMER_ADDR, CONSTANTS.PROTOCOL.PACKET_TYPE.STRIKE))

    def stop(self, _source: int, _dest: int, _payload: bytes) -> bool:
        LOG.info("stop")
        self.set_mode(CONSTANTS.MODES.SLEEP)
        return False
