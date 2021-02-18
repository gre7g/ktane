from machine import Pin

from hardware import KtaneHardware

# Constants:
POSTS = (2, 3, 4, 5, 6, 7)
WIRES = (10, 11, 12, 13, 14, 16, 17, 18, 19, 20)


class WireModule(KtaneHardware):
    def __init__(self, addr: int) -> None:
        KtaneHardware.__init__(self, addr)
        self.posts = [Pin(pin_num, Pin.IN, Pin.PULL_UP) for pin_num in POSTS]
        self.wires = [Pin(pin_num, Pin.OUT) for pin_num in WIRES]

        # Map them
        self.mapping = [None] * len(POSTS)
        for index1 in range(len(WIRES)):
            for index2, wire in enumerate(self.wires):
                wire.value(index1 != index2)
            for index2, post in enumerate(self.posts):
                if not post.value():
                    self.mapping[index2] = index1
                    break
