import logging
import os
from serial import Serial
import subprocess
from time import time

from ktane_lib.constants import CONSTANTS

# Constants:
MP3_PLAYER = "mpg321"
MP3_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mp3s")


def play(filename: str, volume: int = 100):
    subprocess.run([MP3_PLAYER, os.path.join(MP3_DIR, filename), "-qg", str(volume)])


if __name__ == "__main__":
    # s = Serial('/dev/ttyS0', 115200, timeout=1)
    old_t = int(time())
    while True:
        t = int(time())
        if t > old_t:
            old_t = t
            play("beep-07a.mp3", 10)
