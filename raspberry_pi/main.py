from machine import Pin
from time import sleep

"""
>>> from time import sleep
>>> from machine import Pin, UART
>>> u=UART(1,115200,tx=Pin(8),rx=Pin(9))
>>> txen=Pin(15,Pin.OUT)
>>> u.write('Hello, world!')
13
>>> def x(s):
...     txen.on()
...     u.write(s)
...     sleep(0.000087*len(s))
...     txen.off()
...
>>> x('Hello, world!')
"""

if __name__ == "__main__":
    gp0 = Pin(0, Pin.OUT)
    while True:
        gp0.on()
        print("onsies")
        sleep(1)
        gp0.off()
        print("offsies")
        sleep(1)
