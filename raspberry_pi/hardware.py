from constants import CONSTANTS
from machine import Pin, UART, Signal, disable_irq, enable_irq, idle
from random import randrange
import struct
from utime import ticks_us

from log import LOG

# Constants:
UART_NUM = 1
TX_PIN = 8
RX_PIN = 9
TX_EN_PIN = 15

STATUS_RED = 28
STATUS_GREEN = 27


class QueuedPacket:
    def __init__(self, dest: int, packet_type: int, payload: bytes = b"") -> None:
        self.dest, self.packet_type, self.payload = dest, packet_type, payload


class KtaneHardware:
    mode: int
    reply_storage: bytes

    def __init__(self, addr: int) -> None:
        self.current_packet = b""
        self.rx_timeout = None
        self.addr = addr
        self.uart = UART(UART_NUM, CONSTANTS.UART.BAUD_RATE, tx=Pin(TX_PIN), rx=Pin(RX_PIN))
        self.tx_en = Pin(TX_EN_PIN, Pin.OUT)
        self.status_red = Signal(Pin(STATUS_RED, Pin.OUT), invert=True)
        self.status_green = Signal(Pin(STATUS_GREEN, Pin.OUT), invert=True)
        self.handlers = {CONSTANTS.PROTOCOL.PACKET_TYPE.STOP: self.stop}
        self.queued = CONSTANTS.QUEUED_TASKS.NOTHING
        self.last_seq_seen = 0
        self.next_retry = None
        self.awaiting_ack_of_seq = self.queued_packet = None
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

    def queue_packet(self, packet: QueuedPacket) -> None:
        self.queued_packet = packet
        self.retry_now(CONSTANTS.PROTOCOL.TIMING.INITIAL_RETRY_US)

    def send_ack(self, dest: int, seq_num: int) -> None:
        self.send(dest, CONSTANTS.PROTOCOL.PACKET_TYPE.ACK, seq_num)

    def send_without_queuing(self, dest: int, packet_type: int, payload: bytes = b"") -> None:
        seq_num = (self.last_seq_seen + 1) & 0xFF
        self.last_seq_seen = seq_num
        self.send(dest, packet_type, seq_num, payload)

    def retry_now(self, retry_time: int = CONSTANTS.PROTOCOL.TIMING.RETRY_US) -> None:
        seq_num = (self.last_seq_seen + 1) & 0xFF
        self.last_seq_seen = self.awaiting_ack_of_seq = seq_num
        self.send(self.queued_packet.dest, self.queued_packet.packet_type, seq_num, self.queued_packet.payload)
        self.next_retry = ticks_us() + retry_time

    def send_block_return_response(self, packet: QueuedPacket):
        self.queued_packet = packet
        self.retry_now()
        while self.queued_packet:
            KtaneHardware.poll(self)  # Just this poll, not subclassed
        return self.reply_storage

    # UART MEMBERS
    #
    # Packet format (little-endian fields):
    #
    # Field      Length     Notes
    # -------    --------   ----------------------------------------------------
    # Length     1          Total packet length not including Length or Checksum
    # Source     2          Packet source address
    # Dest       2          Packet destination address
    # Type       1          Message type
    # SeqNum     1          Sequence number
    # Payload    variable   Content depends on message type
    # Checksum   2          Checksum such that when all bytes of the message (including Checksum) are summed, the total
    #                       will be 0xFFFF
    def poll(self) -> None:
        """Poll UART"""
        was_idle = True

        # Any UART data waiting?
        available = self.uart.any()
        buffered = len(self.current_packet)
        if available:
            was_idle = False
            if buffered == 0:
                self.current_packet = self.uart.read(1)
                buffered = 1
                available -= 1
        elif self.rx_timeout and (ticks_us() > self.rx_timeout):
            # Aborted or scrambled packet
            LOG.warning("packet aborted")
            self.current_packet = b""
            self.rx_timeout = None

        if available:
            length = 1 + self.current_packet[0] + 2  # Length, packet, checksum
            if length < CONSTANTS.PROTOCOL.MIN_PACKET_LEN:
                # Too short to be a real packet. Discard it.
                self.current_packet = b""
            else:
                if (buffered + available) < length:
                    # Some more. Read it and re-queue.
                    self.current_packet += self.uart.read(available)
                    self.rx_timeout = ticks_us() + CONSTANTS.UART.TWO_FRAMES_US
                else:
                    # The rest is ready
                    self.current_packet += self.uart.read(length - buffered)
                    self.rx_timeout = None

                    # Is the checksum okay?
                    (checksum,) = struct.unpack("<H", self.current_packet[-2:])
                    checksum += sum(self.current_packet[:-2])
                    if checksum == 0xFFFF:
                        # Checksum is okay. Save the sequence number.
                        source, dest, packet_type, seq_num = struct.unpack("<HHBB", self.current_packet[1:7])
                        payload = self.current_packet[7:-2]
                        if (packet_type & CONSTANTS.PROTOCOL.PACKET_TYPE.RESPONSE_MASK) == 0:
                            self.last_seq_seen = seq_num

                        # Is it for us?
                        if (
                            (dest == self.addr)
                            or (dest == CONSTANTS.MODULES.BROADCAST_ALL)
                            or (dest == (self.addr | CONSTANTS.MODULES.BROADCAST_MASK))
                        ):
                            # Yes, for us. Was it a response?
                            if (
                                self.queued_packet
                                and (packet_type & CONSTANTS.PROTOCOL.PACKET_TYPE.RESPONSE_MASK)
                                and (source == self.queued_packet.dest)
                                and (seq_num == self.awaiting_ack_of_seq)
                            ):
                                self.queued_packet = self.awaiting_ack_of_seq = self.next_retry = None
                                self.reply_storage = payload

                            # Do we have a handler?
                            handler = self.handlers.get(packet_type)
                            if handler:
                                # We have a handler. Hand off the packet. It will return a True if it took care of
                                # ACKing.
                                if not handler(source, dest, payload) and (
                                    (dest & CONSTANTS.MODULES.BROADCAST_MASK) != CONSTANTS.MODULES.BROADCAST_MASK
                                ):
                                    self.send_ack(source, seq_num)

                    self.current_packet = b""

        # Need to retry?
        if (self.next_retry is not None) and (ticks_us() >= self.next_retry):
            self.retry_now()

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

        if was_idle:
            idle()

    def poll_forever(self):
        while True:
            self.poll()

    def send(self, dest: int, packet_type: int, seq_num: int, payload: bytes = b"") -> None:
        """Send a packet"""
        # Is anything inbound?
        while self.uart.any():
            # Yes, give it a chance to arrive instead of clobbering it

            back_off = ticks_us() + (
                randrange(*CONSTANTS.PROTOCOL.TIMING.BCAST_REPLY_BACKOFF)
                if packet_type == CONSTANTS.PROTOCOL.PACKET_TYPE.RESPONSE_ID
                else randrange(*CONSTANTS.PROTOCOL.TIMING.BACKOFF_TIME)
            )
            while ticks_us() < back_off:
                self.poll()

        # Send packet
        data = struct.pack("<BHHBB", 2 + 2 + 1 + 1 + len(payload), self.addr, dest, packet_type, seq_num) + payload
        data += struct.pack("<H", 0xFFFF - sum(data))
        done = ticks_us() + (len(data) * CONSTANTS.UART.ONE_FRAME_US)
        self.tx_en.on()
        self.uart.write(data)
        while ticks_us() < done:
            idle()
        self.tx_en.off()

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
