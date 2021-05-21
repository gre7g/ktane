from machine import Pin, UART, lightsleep
from math import ceil
from random import randrange
import struct
from time import time


class LOG:
    # debug = print
    debug = lambda *args: None
    info = print
    # info = lambda *args: None
    warning = print
    # warning = lambda *args: None


# Constants:
UART_NUM = 1
BAUD_RATE = 115200
TX_PIN = 8
RX_PIN = 9
TX_EN_PIN = 15
ONE_FRAME = 10 / BAUD_RATE * 1000.0
TWO_FRAMES = int(ceil(10 / BAUD_RATE * 1000.0))
BACKOFF_TIME = (1, 5)
BCAST_REPLY_BACKOFF = (1, 50)
INITIAL_RETRY_TIME = 2  # 2s
RETRY_TIME = 1  # 1s
TIMER_ADDR = 0x0000
BROADCAST_ALL = 0xFFFF
BROADCAST_MASK = 0x00FF

STATUS_RED = 28
STATUS_GREEN = 27

MODE_SLEEP = 0
MODE_READY = 1
MODE_ARMED = 2
MODE_DISARMED = 3

PT_RESPONSE_MASK = 0x80
PT_ACK = 0x80
PT_REQUEST_ID = 0x01
PT_RESPONSE_ID = 0x81
PT_STOP = 0x02
PT_CONFIGURE = 0x03
PT_START = 0x04
PT_STRIKE = 0x05
PT_ERROR = 0x06
PT_DISARMED = 0x07
PT_NEEDY = 0x08
PT_READ_STATUS = 0x09
PT_STATUS = 0x89
PT_SOUND = 0x0A

MT_TIMER = 0x00
MT_WIRES = 0x01
MT_BUTTON = 0x02
MT_KEYPAD = 0x03
MT_SIMON = 0x04
MT_MORSE = 0x07

FLAG_TRIGGER = 0x01
FLAG_NEEDY = 0x02
FLAG_EXCLUSIVE = 0x04

SOUND_HALT = 0
SOUND_SIMON_1 = 1
SOUND_SIMON_2 = 2
SOUND_SIMON_3 = 3
SOUND_SIMON_4 = 4
SOUND_TIMER_LOW = 5
SOUND_BUTTON_1 = 6
SOUND_BUTTON_2 = 7
SOUND_TUNE_UP = 8
SOUND_TUNE_DOWN = 9
SOUND_VENT = 10
SOUND_START_CAP_1 = 11
SOUND_START_CAP_2 = 12
SOUND_START_CAP_3 = 13
SOUND_START_CAP_4 = 14
SOUND_MORSE_A = 15
SOUND_MORSE_Z = 40


class QueuedPacket:
    def __init__(self, dest: int, packet_type: int, payload: bytes = b"") -> None:
        self.dest, self.packet_type, self.payload = dest, packet_type, payload


class KtaneHardware:
    mode: int
    reply_storage: bytes

    def __init__(self, addr: int) -> None:
        self.addr = addr
        self.uart = UART(UART_NUM, BAUD_RATE, tx=Pin(TX_PIN), rx=Pin(RX_PIN))
        self.tx_en = Pin(TX_EN_PIN, Pin.OUT)
        self.status_red = Pin(STATUS_RED, Pin.IN)
        self.status_green = Pin(STATUS_GREEN, Pin.IN)
        self.handlers = {PT_STOP: self.stop}
        self.last_seq_seen = 0
        self.next_retry = None
        self.awaiting_ack_of_seq = self.queued_packet = None
        self.set_mode(MODE_SLEEP)

    def set_mode(self, mode: int) -> None:
        self.mode = mode
        if mode == MODE_SLEEP:
            LOG.info("mode=sleep")
            self.status_green.init(Pin.IN)
            self.status_red.init(Pin.IN)
        elif mode in [MODE_ARMED, MODE_READY]:
            LOG.info("mode=armed or ready")
            self.status_green.init(Pin.IN)
            self.status_red.init(Pin.OUT)
            self.status_red.off()  # active low
        elif mode == MODE_DISARMED:
            LOG.info("mode=disarmed")
            self.status_green.init(Pin.OUT)
            self.status_red.init(Pin.IN)
            self.status_green.off()  # active low

    def queue_packet(self, packet: QueuedPacket) -> None:
        self.queued_packet = packet
        self.retry_now(INITIAL_RETRY_TIME)

    def send_ack(self, dest: int, seq_num: int) -> None:
        self.send(dest, PT_ACK, seq_num)

    def send_without_queuing(self, dest: int, packet_type: int, payload: bytes = b"") -> None:
        seq_num = (self.last_seq_seen + 1) & 0xFF
        self.last_seq_seen = seq_num
        self.send(dest, packet_type, seq_num, payload)

    def retry_now(self, retry_time: int = RETRY_TIME) -> None:
        seq_num = (self.last_seq_seen + 1) & 0xFF
        self.last_seq_seen = self.awaiting_ack_of_seq = seq_num
        self.send(self.queued_packet.dest, self.queued_packet.packet_type, seq_num, self.queued_packet.payload)
        self.next_retry = time() + retry_time

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
        # Any UART data waiting?
        if self.uart.any():
            # Yes, read length
            packet: bytes = self.uart.read(1)
            if packet != b"\x00":
                length = 1 + packet[0] + 2  # Length, packet, checksum

                # Read remainder
                while len(packet) < length:
                    # Anything queued?
                    if self.uart.any():
                        # Read it in
                        packet += self.uart.read(1)
                    else:
                        # Nothing is queued. Wait two frame times.
                        lightsleep(TWO_FRAMES)

                        # Is anything queued now?
                        if not self.uart.any():
                            # Still nothing, abort the packet
                            LOG.warning("packet aborted %r" % packet)
                            break
                else:
                    # Is the checksum okay?
                    (checksum,) = struct.unpack("<H", packet[-2:])
                    checksum += sum(packet[:-2])
                    if checksum == 0xFFFF:
                        # Checksum is okay. Save the sequence number.
                        source, dest, packet_type, seq_num = struct.unpack("<HHBB", packet[1:7])
                        payload = packet[7:-2]
                        if (packet_type & PT_RESPONSE_MASK) == 0:
                            self.last_seq_seen = seq_num

                        # Is it for us?
                        if (dest == self.addr) or (dest == BROADCAST_ALL) or (dest == (self.addr | BROADCAST_MASK)):
                            # Yes, for us. Was it a response?
                            if (
                                self.queued_packet
                                and (packet_type & PT_RESPONSE_MASK)
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
                                if not handler(source, dest, payload) and ((dest & BROADCAST_MASK) != BROADCAST_MASK):
                                    self.send_ack(source, seq_num)

        # Need to retry?
        if (self.next_retry is not None) and (time() >= self.next_retry):
            self.retry_now()

    def poll_forever(self):
        while True:
            self.poll()

    def send(self, dest: int, packet_type: int, seq_num: int, payload: bytes = b"") -> None:
        """Send a packet"""
        # Is anything inbound?
        while self.uart.any():
            # Yes, give it a chance to arrive instead of clobbering it
            self.poll()

            # Random backoff
            lightsleep(randrange(*BCAST_REPLY_BACKOFF) if packet_type == PT_RESPONSE_ID else randrange(*BACKOFF_TIME))

        # Send packet
        data = struct.pack("<BHHBB", 2 + 2 + 1 + 1 + len(payload), self.addr, dest, packet_type, seq_num) + payload
        data += struct.pack("<H", 0xFFFF - sum(data))
        delay = len(data) * ONE_FRAME
        self.tx_en.on()
        self.uart.write(data)
        lightsleep(int(ceil(delay)))
        self.tx_en.off()

    def unable_to_arm(self) -> None:
        LOG.info("error")
        self.queue_packet(QueuedPacket(TIMER_ADDR, PT_ERROR))

    def disarmed(self):
        LOG.info("disarmed")
        self.queue_packet(QueuedPacket(TIMER_ADDR, PT_DISARMED))
        self.set_mode(MODE_DISARMED)

    def strike(self):
        LOG.info("strike")
        self.queue_packet(QueuedPacket(TIMER_ADDR, PT_STRIKE))

    def stop(self, _source: int, _dest: int, _payload: bytes) -> bool:
        LOG.info("stop")
        self.set_mode(MODE_SLEEP)
        return False
