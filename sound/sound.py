import logging
import os
import struct

from RPi import GPIO
from serial import Serial
import subprocess
from time import time, sleep

from ktane_lib.constants import CONSTANTS
from ktane_lib.ktane_base import KtaneBase

# Constants:
LOG = logging.getLogger(__file__)
MP3_PLAYER = "mpg321"
MP3_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mp3s")
TX_EN_PIN = 7
IDLE_SLEEP = 0.000050  # 50us
RUN_TIME = 70  # 70s


def play(filename: str, volume: int = 100):
    subprocess.run([MP3_PLAYER, os.path.join(MP3_DIR, filename), "-qg", str(volume)])


def ticks_us():
    return int(time() * 1000000)


class Pin:
    def __init__(self, pin_num: int, pin_type: int):
        self.pin_num = pin_num
        GPIO.setup(pin_num, pin_type)

    def on(self):
        GPIO.output(self.pin_num, True)

    def off(self):
        GPIO.output(self.pin_num, False)


def idle():
    sleep(IDLE_SLEEP)


class SoundModule(KtaneBase):
    def __init__(self):
        uart = PiSerial("/dev/ttyS0", 115200, timeout=1)
        tx_en = Pin(TX_EN_PIN, GPIO.OUT)
        KtaneBase.__init__(self, CONSTANTS.MODULES.TYPES.SOUND, uart, tx_en, LOG, idle, ticks_us)
        self.handlers.update(
            {
                # CONSTANTS.PROTOCOL.PACKET_TYPE.REQUEST_ID: self.request_id,
                CONSTANTS.PROTOCOL.PACKET_TYPE.START: self.start,
                CONSTANTS.PROTOCOL.PACKET_TYPE.STOP: self.stop,
            }
        )
        self.game_ends_at = None

    def start(self, _source: int, _dest: int, _payload: bytes):
        # Payload is the difficulty but we're not adjustable so we ignore it
        LOG.debug("start")
        self.game_ends_at = time() + RUN_TIME
        self.queued |= CONSTANTS.QUEUED_TASKS.SEND_TIME

    def check_queued_tasks(self, was_idle):
        if self.queued & CONSTANTS.QUEUED_TASKS.SEND_TIME:
            LOG.debug("send_time")
            was_idle = False
            self.queued &= ~CONSTANTS.QUEUED_TASKS.SEND_TIME
            seq_num = (self.last_seq_seen + 1) & 0xFF
            self.last_seq_seen = seq_num
            payload = struct.pack("<L", int((self.game_ends_at - time()) * 1000000))
            self.send(CONSTANTS.MODULES.TYPES.TIMER << 8, CONSTANTS.PROTOCOL.PACKET_TYPE.SET_TIME, seq_num, payload)

        if was_idle:
            self.idle()

    # def request_id(self, source: int, _dest: int, _payload: bytes) -> bool:
    #     LOG.debug("request_id")
    #     Timer(
    #         mode=Timer.ONE_SHOT,
    #         period=randrange(*CONSTANTS.PROTOCOL.TIMING.ID_SPREAD_MS),
    #         callback=lambda timer: self.send_without_queuing(
    #             source,
    #             CONSTANTS.PROTOCOL.PACKET_TYPE.RESPONSE_ID,
    #             struct.pack("BB", CONSTANTS.MODULES.FLAGS.TRIGGER, 0),
    #         ),
    #     )
    #     return True


class PiSerial(Serial):
    def any(self):
        return self.in_waiting


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    GPIO.setmode(GPIO.BOARD)
    sound = SoundModule()
    sound.poll_forever()
    # old_t = int(time())
    # while True:
    #     t = int(time())
    #     if t > old_t:
    #         old_t = t
    #         play("beep-07a.mp3", 10)
