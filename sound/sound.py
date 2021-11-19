import logging
import os
import struct

from RPi import GPIO
from serial import Serial
import subprocess
from time import time, sleep

from ktane_lib.constants import CONSTANTS
from ktane_lib.ktane_base import KtaneBase, QueuedPacket

# Constants:
LOG = logging.getLogger(__file__)
MP3_PLAYER = "mpg321"
MP3_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mp3s")
TX_EN_PIN = 7
IDLE_SLEEP = 0.000050  # 50us
BEEP_OFFSET = -0.1  # -100ms
RESYNC_EVERY = 10  # 10s
NUM_STRIKES = 3


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
        self.modules = [CONSTANTS.MODULES.TYPES.WIRES << 8]  # TODO: make dynamic
        uart = PiSerial("/dev/ttyS0", 115200, timeout=1)
        tx_en = Pin(TX_EN_PIN, GPIO.OUT)
        KtaneBase.__init__(self, CONSTANTS.MODULES.TYPES.SOUND, uart, tx_en, LOG, idle, ticks_us)
        self.handlers.update(
            {
                # CONSTANTS.PROTOCOL.PACKET_TYPE.REQUEST_ID: self.request_id,
                CONSTANTS.PROTOCOL.PACKET_TYPE.START: self.start,
                CONSTANTS.PROTOCOL.PACKET_TYPE.ERROR: self.error,
                CONSTANTS.PROTOCOL.PACKET_TYPE.STOP: self.stop,
                CONSTANTS.PROTOCOL.PACKET_TYPE.SHOW_TIME: self.show_time,
                CONSTANTS.PROTOCOL.PACKET_TYPE.DISARMED: self.disarmed,
                CONSTANTS.PROTOCOL.PACKET_TYPE.STRIKE: self.strike,
                CONSTANTS.PROTOCOL.PACKET_TYPE.STATUS: self.status,
            }
        )
        self.game_time = self.game_ends_at = self.next_beep_at = self.next_resync = self.strikes = None
        self.armed_modules = set()

    def start(self, _source: int, _dest: int, _payload: bytes):
        # Payload is the difficulty but we're not adjustable so we ignore it
        LOG.debug("start")
        now = time()
        self.game_ends_at = now + self.game_time
        self.next_beep_at = now + 1.0 - BEEP_OFFSET
        self.next_resync = now + RESYNC_EVERY
        self.queued |= CONSTANTS.QUEUED_TASKS.SEND_TIME
        self.strikes = 0
        self.armed_modules = set(self.modules)

    def stop(self, _source: int = 0, _dest: int = 0, _payload: bytes = b""):
        LOG.debug("stop")
        self.game_ends_at = self.next_beep_at = self.next_resync = None

    def show_time(self, _source: int, _dest: int, _payload: bytes):
        LOG.debug("show_time")
        (game_time_us,) = struct.unpack("<L", _payload)
        self.game_time = game_time_us / 1000000
        play(CONSTANTS.SOUNDS.FILES.TIMER_TICK, CONSTANTS.SOUNDS.FILES.TIMER_TICK_VOL)

    def error(self, _source: int, _dest: int, _payload: bytes):
        LOG.debug("error")
        self.send_without_queuing(CONSTANTS.MODULES.BROADCAST_ALL, CONSTANTS.PROTOCOL.PACKET_TYPE.STOP)
        self.stop()
        play(CONSTANTS.SOUNDS.FILES.STRIKE, CONSTANTS.SOUNDS.FILES.STRIKE_VOL)

    def disarmed(self, _source: int, _dest: int, _payload: bytes):
        LOG.debug("disarmed")
        self.armed_modules.discard(_source)
        if self.all_modules_disarmed():
            self.send_without_queuing(CONSTANTS.MODULES.BROADCAST_ALL, CONSTANTS.PROTOCOL.PACKET_TYPE.STOP)
            self.stop()
        else:
            self.next_beep_at += 1.0
        play(CONSTANTS.SOUNDS.FILES.DISARMED, CONSTANTS.SOUNDS.FILES.DISARMED_VOL)

    def all_modules_disarmed(self):
        return not self.armed_modules

    def strike(self, _source: int, _dest: int, _payload: bytes):
        LOG.debug("strike")
        self.strikes += 1
        if self.strikes >= NUM_STRIKES:
            self.explode()
        else:
            play(CONSTANTS.SOUNDS.FILES.STRIKE, CONSTANTS.SOUNDS.FILES.STRIKE_VOL)
            if self.next_beep_at:
                self.next_beep_at += 1.0

    def status(self, _source: int, _dest: int, _payload: bytes):
        # Payload:
        #
        # Field     Length   Notes
        # -------   ------   -----------------------------------------
        # running   1        True is the game is in play
        # strikes   1        Number of strikes
        # time      5        Time as a string, like " 1:12" or "16.92"
        time_left = self.game_ends_at - time()
        if time_left >= 60.0:
            time_string = "%2d:%02d" % (int(time_left / 60.0), int(time_left) % 60)
        else:
            time_string = "%5.2f" % time_left
        payload = struct.pack("?B5s", self.game_ends_at is not None, self.strikes, time_string)
        self.send_without_queuing(
            _source, CONSTANTS.PROTOCOL.PACKET_TYPE.STATUS | CONSTANTS.PROTOCOL.PACKET_TYPE.RESPONSE_MASK, payload
        )

    def check_queued_tasks(self, was_idle):
        now = time()

        if self.queued & CONSTANTS.QUEUED_TASKS.SEND_TIME:
            LOG.debug("set_time")
            was_idle = False
            self.queued &= ~CONSTANTS.QUEUED_TASKS.SEND_TIME
            self.set_time(now)

        if self.next_beep_at and (now >= self.next_beep_at):
            LOG.debug("beep")
            play(CONSTANTS.SOUNDS.FILES.TIMER_TICK, CONSTANTS.SOUNDS.FILES.TIMER_TICK_VOL)
            self.next_beep_at += 1.0
            if self.next_beep_at > self.game_ends_at:
                self.next_beep_at = None

        if self.next_resync and (now >= self.next_resync):
            LOG.debug("resync")
            was_idle = False
            self.set_time(now)
            self.next_resync += RESYNC_EVERY

        if self.game_ends_at and (now >= self.game_ends_at):
            LOG.debug("game_ends")
            was_idle = False
            self.explode()

        if was_idle:
            self.idle()

    def set_time(self, now: float):
        payload = struct.pack("<L", int((self.game_ends_at - now) * 1000000))
        self.queue_packet(
            QueuedPacket(CONSTANTS.MODULES.TYPES.TIMER << 8, CONSTANTS.PROTOCOL.PACKET_TYPE.SET_TIME, payload)
        )

    def explode(self):
        self.send_without_queuing(CONSTANTS.MODULES.BROADCAST_ALL, CONSTANTS.PROTOCOL.PACKET_TYPE.STOP)
        self.stop()
        play(CONSTANTS.SOUNDS.FILES.EXPLOSION, CONSTANTS.SOUNDS.FILES.EXPLOSION_VOL)

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
