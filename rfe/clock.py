# Constants:

# RF200
GPIO_0 = 7
GPIO_1 = 6
GPIO_2 = 5
GPIO_3 = 16
GPIO_4 = 17
GPIO_5 = 20
GPIO_6 = 21
GPIO_7 = 10
GPIO_8 = 11
GPIO_9 = 12
GPIO_10 = 23
GPIO_11 = 24
GPIO_12 = 25
GPIO_13 = 26
GPIO_14 = 18  # with PA else 27
GPIO_15 = 28
GPIO_16 = 29
GPIO_17 = 30
GPIO_18 = 31
GPIO_19 = 19

COLON = GPIO_4
PIEZO2 = GPIO_5  # OC3B
PIEZO1 = GPIO_6  # OC3C
COM_CATH1 = GPIO_7
COM_CATH2 = GPIO_8
AN1_1200 = GPIO_14
JOINT = GPIO_15
AN2_1200 = GPIO_16
SNOOZE = GPIO_17

# Timer3
TCCR3A = 0x90
TCCR3B = 0x91
TCCR3C = 0x92
OC3AH = 0x99
OC3AL = 0x98
OC3BH = 0x9B
OC3BL = 0x9A
OC3CH = 0x9D
OC3CL = 0x9C

ANNOYING_CYCLE = 0xFFE0  # Bit mask of beep/quiet

STATE_START1 = 0
STATE_START2 = 1
STATE_OFF = 2
STATE_1200_P1 = 3
STATE_1200_P2 = 4
STATE_COLON_P1 = 5
STATE_COLON_P2 = 6

# Globals:
G_BEEP_CYCLE = 0
G_STATE = STATE_START1
G_SYNCD = True


@setHook(HOOK_STARTUP)
def on_startup():
    # Configure Timer3 (piezo 5555Hz output)
    setPinDir(PIEZO1, True)
    setPinDir(PIEZO2, True)
    writePin(PIEZO1, False)
    writePin(PIEZO2, False)
    poke(TCCR3B, 0x0A)  # 0x0A -> TCCR3B, clk/8
    poke(OC3AH, 0x00)  # 0x05 -> OC3CH (16MHz / 8 / 180 = 11,111Hz)
    poke(OC3AL, 0xB4)  # 0xBD -> OC3CL
    poke(OC3BH, 0)
    poke(OC3BL, 1)
    poke(OC3CH, 0)
    poke(OC3CL, 1)

    setPinDir(SNOOZE, False)

    writePin(COLON, False)
    writePin(COM_CATH1, False)
    writePin(COM_CATH2, False)
    writePin(AN1_1200, False)
    writePin(AN2_1200, False)
    writePin(JOINT, False)

    setPinDir(COLON, True)
    setPinDir(COM_CATH1, True)
    setPinDir(COM_CATH2, True)
    setPinDir(AN2_1200, True)
    setPinDir(AN1_1200, True)
    setPinDir(JOINT, True)

    monitorPin(SNOOZE, True)


def alarm():
    global G_BEEP_CYCLE

    G_BEEP_CYCLE = ANNOYING_CYCLE


def show_clock(on):
    global G_STATE

    G_STATE = STATE_1200_P1 if on else STATE_OFF


@setHook(HOOK_GPIN)
def on_gpin(pin, level):
    global G_BEEP_CYCLE

    G_BEEP_CYCLE = 0


def beep_on():
    global G_SYNCD

    poke(TCCR3A, 0x14)  # 0x14 -> TCCR3A, toggle OC3C & OC3B on match, CRC, TOP=OCR3A
    if G_SYNCD:
        poke(TCCR3C, 0x40)  # Toggle OC3B
        G_SYNCD = False


def beep_off():
    poke(TCCR3A, 0)


@setHook(HOOK_1S)
def on_1s():
    global G_STATE

    if G_STATE == STATE_OFF:
        pass
    elif (G_STATE == STATE_1200_P1) or (G_STATE == STATE_1200_P2):
        G_STATE = STATE_COLON_P1
    elif (G_STATE == STATE_COLON_P1) or (G_STATE == STATE_COLON_P2):
        G_STATE = STATE_1200_P1
    elif (G_STATE == STATE_START1) or (G_STATE == STATE_START2):
        G_STATE = STATE_OFF


@setHook(HOOK_10MS)
def on_10ms(t):
    global G_STATE

    if G_STATE == STATE_OFF:
        writePin(COLON, False)
        writePin(COM_CATH1, False)
        writePin(COM_CATH2, False)
        writePin(AN1_1200, False)
        writePin(AN2_1200, False)
        writePin(JOINT, False)
    elif G_STATE == STATE_1200_P1:
        writePin(COLON, False)
        writePin(COM_CATH1, True)
        writePin(COM_CATH2, False)
        writePin(AN1_1200, True)
        writePin(AN2_1200, False)
        writePin(JOINT, True)
        G_STATE = STATE_1200_P2
    elif G_STATE == STATE_1200_P2:
        writePin(COLON, False)
        writePin(COM_CATH1, False)
        writePin(COM_CATH2, True)
        writePin(AN1_1200, False)
        writePin(AN2_1200, True)
        writePin(JOINT, True)
        G_STATE = STATE_1200_P1
    elif G_STATE == STATE_COLON_P1:
        writePin(COLON, True)
        writePin(COM_CATH1, True)
        writePin(COM_CATH2, False)
        writePin(AN1_1200, False)
        writePin(AN2_1200, False)
        writePin(JOINT, False)
        G_STATE = STATE_COLON_P2
    elif G_STATE == STATE_COLON_P2:
        writePin(COLON, False)
        writePin(COM_CATH1, False)
        writePin(COM_CATH2, True)
        writePin(AN1_1200, False)
        writePin(AN2_1200, False)
        writePin(JOINT, False)
        G_STATE = STATE_COLON_P1
    elif G_STATE == STATE_START1:
        writePin(COLON, False)
        writePin(COM_CATH1, True)
        writePin(COM_CATH2, False)
        writePin(AN1_1200, False)
        writePin(AN2_1200, True)
        writePin(JOINT, False)
        G_STATE = STATE_START2
    elif G_STATE == STATE_START2:
        writePin(COLON, False)
        writePin(COM_CATH1, False)
        writePin(COM_CATH2, True)
        writePin(AN1_1200, False)
        writePin(AN2_1200, False)
        writePin(JOINT, False)
        G_STATE = STATE_START1


@setHook(HOOK_100MS)
def on_100ms(t):
    global G_BEEP_CYCLE

    if G_BEEP_CYCLE & 0x8000:
        G_BEEP_CYCLE = (G_BEEP_CYCLE << 1) | 1
        beep_on()
    else:
        G_BEEP_CYCLE = G_BEEP_CYCLE << 1
        beep_off()



#07afa4
#079f1b
#8/bace/0xd1f/1/|\x8dH<\xd0c\xfd\x94\xb1\xb6\x8d\x8f\x83\x1e\x17\xb1
# bottom of 2 (2d-12), topright of first 0 (3b-16)
