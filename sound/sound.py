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
BEEP_OFFSET = -0.1  # -100ms
RESYNC_EVERY = 10  # 10s


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
                CONSTANTS.PROTOCOL.PACKET_TYPE.SHOW_TIME: self.show_time,
                CONSTANTS.PROTOCOL.PACKET_TYPE.DISARMED: self.disarmed,
                CONSTANTS.PROTOCOL.PACKET_TYPE.STRIKE: self.strike,
            }
        )
        self.game_time = self.game_ends_at = self.next_beep_at = self.next_resync = None

    def start(self, _source: int, _dest: int, _payload: bytes):
        # Payload is the difficulty but we're not adjustable so we ignore it
        LOG.debug("start")
        now = time()
        self.game_ends_at = now + self.game_time
        self.next_beep_at = now + 1.0 - BEEP_OFFSET
        self.next_resync = now + RESYNC_EVERY
        self.queued |= CONSTANTS.QUEUED_TASKS.SEND_TIME

    def stop(self, _source: int = 0, _dest: int = 0, _payload: bytes = b""):
        LOG.debug("stop")
        self.game_ends_at = self.next_beep_at = self.next_resync = None

    def show_time(self, _source: int, _dest: int, _payload: bytes):
        LOG.debug("show_time")
        game_time_us, = struct.unpack("<L", _payload)
        self.game_time = game_time_us / 1000000
        play(CONSTANTS.SOUNDS.FILES.TIMER_TICK, CONSTANTS.SOUNDS.FILES.TIMER_TICK_VOL)

    def disarmed(self, _source: int, _dest: int, _payload: bytes):
        LOG.debug("disarmed")
        play(CONSTANTS.SOUNDS.FILES.DISARMED, CONSTANTS.SOUNDS.FILES.DISARMED_VOL)

    def strike(self, _source: int, _dest: int, _payload: bytes):
        LOG.debug("strike")
        play(CONSTANTS.SOUNDS.FILES.STRIKE, CONSTANTS.SOUNDS.FILES.STRIKE_VOL)

    def check_queued_tasks(self, was_idle):
        if self.queued & CONSTANTS.QUEUED_TASKS.SEND_TIME:
            LOG.debug("send_time")
            was_idle = False
            self.queued &= ~CONSTANTS.QUEUED_TASKS.SEND_TIME
            seq_num = (self.last_seq_seen + 1) & 0xFF
            self.last_seq_seen = seq_num
            payload = struct.pack("<L", int((self.game_ends_at - time()) * 1000000))
            self.send(CONSTANTS.MODULES.TYPES.TIMER << 8, CONSTANTS.PROTOCOL.PACKET_TYPE.SET_TIME, seq_num, payload)

        now = time()

        if self.next_beep_at and (now >= self.next_beep_at):
            LOG.debug("beep")
            play(CONSTANTS.SOUNDS.FILES.TIMER_TICK, CONSTANTS.SOUNDS.FILES.TIMER_TICK_VOL)
            self.next_beep_at += 1.0
            if self.next_beep_at > self.game_ends_at:
                self.next_beep_at = None

        if self.next_resync and (now >= self.next_resync):
            LOG.debug("resync")
            seq_num = (self.last_seq_seen + 1) & 0xFF
            self.last_seq_seen = seq_num
            payload = struct.pack("<L", int((self.game_ends_at - now) * 1000000))
            self.send(CONSTANTS.MODULES.TYPES.TIMER << 8, CONSTANTS.PROTOCOL.PACKET_TYPE.SET_TIME, seq_num, payload)
            self.next_resync += RESYNC_EVERY

        if self.game_ends_at and (now >= self.game_ends_at):
            LOG.debug("game_ends")
            seq_num = (self.last_seq_seen + 1) & 0xFF
            self.last_seq_seen = seq_num
            self.send(CONSTANTS.MODULES.BROADCAST_ALL, CONSTANTS.PROTOCOL.PACKET_TYPE.STOP, seq_num)
            self.stop()
            play(CONSTANTS.SOUNDS.FILES.EXPLOSION, CONSTANTS.SOUNDS.FILES.EXPLOSION_VOL)

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
