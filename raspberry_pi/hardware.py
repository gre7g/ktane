from machine import Pin, UART, lightsleep
from math import ceil
from random import randrange
import struct

# Constants:
UART_NUM = 1
BAUD_RATE = 115200
TX_PIN = 8
RX_PIN = 9
TX_EN_PIN = 15
ONE_FRAME = 10 / BAUD_RATE * 1000.0
TWO_FRAMES = int(ceil(10 / BAUD_RATE * 1000.0))
BACKOFF_TIME = (1, 5)
STATUS_RED = 27
STATUS_GREEN = 28

MODE_SLEEP = 0
MODE_READY = 1
MODE_ARMED = 2
MODE_DISARMED = 3

MT_REQUEST_ID = 0
MT_RESPONSE_ID = 1
MT_ACK = 2
MT_STOP = 3
MT_CONFIGURE = 4
MT_START = 5
MT_STRIKE = 6
MT_ERROR = 7
MT_DEFUSED = 8
MT_NEEDY = 9
MT_READ_STATUS = 10
MT_STATUS = 11
MT_SOUND = 12

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


class KtaneHardware:
    def __init__(self, addr: int) -> None:
        self.addr = addr
        self.mode = MODE_SLEEP
        self.uart = UART(UART_NUM, BAUD_RATE, tx=Pin(TX_PIN), rx=Pin(RX_PIN))
        self.tx_en = Pin(TX_EN_PIN, Pin.OUT)
        self.status_red = Pin(STATUS_RED, Pin.IN)
        self.status_green = Pin(STATUS_GREEN, Pin.IN)
        self.handlers = {}

    def set_mode(self, mode: int) -> None:
        if mode == MODE_SLEEP:
            self.status_green.init(Pin.IN)
            self.status_red.init(Pin.IN)
        elif mode in [MODE_ARMED, MODE_READY]:
            self.status_green.init(Pin.IN)
            self.status_red.init(Pin.OUT)
            self.status_red.off()  # active low
        elif mode == MODE_DISARMED:
            self.status_green.init(Pin.OUT)
            self.status_red.init(Pin.IN)
            self.status_green.off()  # active low

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
            length = 1 + packet[0] + 2  # Length, packet, checksum

            # Read remainder
            while len(packet) < length:
                # How much is queued?
                available = min(self.uart.any(), length - len(packet))
                if available:
                    # Read it in
                    packet += self.uart.read(available)
                else:
                    # Nothing is queued. Wait two frame times.
                    lightsleep(TWO_FRAMES)

                    # Is anything queued now?
                    if self.uart.any() == 0:
                        # Still nothing, abort the packet
                        break
            else:
                # Check the packet type
                handler = self.handlers.get(packet[5])
                if handler:
                    # Valid type. Is the checksum okay?
                    (checksum,) = struct.unpack("<H", packet[-2:])
                    checksum += sum(packet[:-2])
                    if checksum == 0xFFFF:
                        # Checksum is okay. Hand off the packet
                        source, dest, seq_num = struct.unpack("<HHxB", packet[1:7])
                        handler(source, dest, packet[7:-2])

    def send(self, dest: int, packet_type: int, seq_num: int, payload: bytes) -> None:
        """Send a packet"""
        # Is anything inbound?
        while self.uart.any():
            # Yes, give it a chance to arrive instead of clobbering it
            self.poll()

            # Random backoff
            lightsleep(randrange(*BACKOFF_TIME))

        # Send packet
        data = struct.pack("<BHHBB", 2 + 2 + 1 + 1 + len(payload), self.addr, dest, packet_type, seq_num) + payload
        data += struct.pack("<H", 0xFFFF - sum(data))
        delay = len(data) * ONE_FRAME
        self.tx_en.on()
        self.uart.write(data)
        lightsleep(int(ceil(delay)))
        self.tx_en.off()
