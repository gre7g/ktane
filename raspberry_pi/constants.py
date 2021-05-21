from math import ceil


class CONSTANTS:
    class COLORS:
        BLACK = 0
        BLUE = 1
        RED = 2
        WHITE = 3
        YELLOW = 4
        GREEN = 5

    class LABELS:
        ABORT=b"ABORT\x00\x00\x00"
        CAR=b"CAR"
        DETONATE=b"DETONATE"
        FKR=b"FKR"
        HOLD=b"HOLD\x00\x00\x00\x00"

    class MODES:
        SLEEP = 0
        READY = 1
        ARMED = 2
        DISARMED = 3

    class MODULES:
        CONFIG_FILENAME = "config.txt"
        TIMER_ADDR = 0x0000
        BROADCAST_ALL = 0xFFFF
        BROADCAST_MASK = 0x00FF

        class TYPES:
            TIMER = 0x00
            WIRES = 0x01
            BUTTON = 0x02
            KEYPAD = 0x03
            SIMON = 0x04
            MORSE = 0x07

        class FLAGS:
            TRIGGER = 0x01
            NEEDY = 0x02
            EXCLUSIVE = 0x04

    class PROTOCOL:
        MIN_PACKET_LEN = 9

        class PACKET_TYPE:
            RESPONSE_MASK = 0x80
            ACK = 0x80
            REQUEST_ID = 0x01
            RESPONSE_ID = 0x81
            STOP = 0x02
            CONFIGURE = 0x03
            START = 0x04
            STRIKE = 0x05
            ERROR = 0x06
            DISARMED = 0x07
            NEEDY = 0x08
            READ_STATUS = 0x09
            STATUS = 0x89
            SOUND = 0x0A

        class TIMING:
            BACKOFF_TIME = (1, 5)
            BCAST_REPLY_BACKOFF = (1, 50)
            INITIAL_RETRY_US = 2000000  # 2s
            RETRY_US = 1000000  # 1s

    class QUEUED_TASKS:
        NOTHING = 0x00
        STRIKE = 0x01
        DISARMED = 0x02
        ASK_TIME=0x04

    class SEVEN_SEGMENT:
        BLANK = 10
        LETTER_R = 11
        LETTER_T = 12
        MASK_BY_DIGIT = [
            0x7E,  # 0
            0x30,  # 1
            0x6D,  # 2
            0x79,  # 3
            0x33,  # 4
            0x5B,  # 5
            0x5F,  # 6
            0x70,  # 7
            0x7F,  # 8
            0x73,  # 9
            0x00,  # BLANK
            0x05,  # LETTER_R
            0x0F,  # LETTER_T
        ]

    class SOUNDS:
        HALT = 0
        SIMON_1 = 1
        SIMON_2 = 2
        SIMON_3 = 3
        SIMON_4 = 4
        TIMER_LOW = 5
        BUTTON_1 = 6
        BUTTON_2 = 7
        TUNE_UP = 8
        TUNE_DOWN = 9
        VENT = 10
        START_CAP_1 = 11
        START_CAP_2 = 12
        START_CAP_3 = 13
        START_CAP_4 = 14
        MORSE_A = 15
        MORSE_Z = 40

    class UART:
        BAUD_RATE = 115200
        ONE_FRAME_US = int(ceil(10 / BAUD_RATE * 1000000.0))
        TWO_FRAMES_US = int(ceil(20 / BAUD_RATE * 1000000.0))
