from serial import Serial
import subprocess
from time import time

if __name__ == "__main__":
    #s = Serial('/dev/ttyS0', 115200, timeout=1)
    old_t = int(time())
    while True:
        t = int(time())
        if t > old_t:
            old_t = t
            subprocess.run(["mpg321", "/home/pi/beep-07a.mp3", "-qg", "10"])
    