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

SNOOZE = GPIO_4
PIEZO1 = GPIO_6  # OC3C
PIEZO2 = GPIO_5  # OC3B
COM_CATH1 = GPIO_7
COM_CATH2 = GPIO_8
AN2_1200 = GPIO_9
AN1_1200 = GPIO_10
AN_1200 = GPIO_11

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

ANNOYING_CYCLE = 0xFFE0

# Globals:
G_BEEP_CYCLE = 0
G_SYNCD = True
G_PHASE = False
G_SHOW_CLOCK = False
G_START_UP = True


@setHook(HOOK_STARTUP)
def on_startup():
    # Configure Timer3 (piezo 5555Hz output)
    setPinDir(PIEZO1, True)
    setPinDir(PIEZO2, True)
    poke(TCCR3B, 0x0A)  # 0x0A -> TCCR3B, clk/8
    poke(OC3AH, 0x00)  # 0x05 -> OC3CH (16MHz / 8 / 180 = 11,111Hz)
    poke(OC3AL, 0xB4)  # 0xBD -> OC3CL
    poke(OC3BH, 0)
    poke(OC3BL, 1)
    poke(OC3CH, 0)
    poke(OC3CL, 1)

    writePin(COM_CATH1, False)
    writePin(COM_CATH2, False)
    writePin(AN2_1200, False)
    writePin(AN1_1200, False)
    writePin(AN_1200, False)
    setPinDir(SNOOZE, False)
    setPinDir(COM_CATH1, True)
    setPinDir(COM_CATH2, True)
    setPinDir(AN2_1200, True)
    setPinDir(AN1_1200, True)
    setPinDir(AN_1200, True)

    monitorPin(SNOOZE, True)
    
    show_clock(True)
    
    
def alarm():
    global G_BEEP_CYCLE

    G_BEEP_CYCLE = ANNOYING_CYCLE


def show_clock(on):
    global G_SHOW_CLOCK
    
    G_SHOW_CLOCK = on
    if not on:
        writePin(COM_CATH1, False)
        writePin(COM_CATH2, False)
        writePin(AN2_1200, False)
        writePin(AN1_1200, False)
        writePin(AN_1200, False)
    

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
    global G_START_UP

    if G_START_UP:
        show_clock(False)
        G_START_UP = False
        

@setHook(HOOK_10MS)
def on_10ms(t):
    global G_PHASE
    
    if G_SHOW_CLOCK:
        if G_PHASE:
            writePin(COM_CATH1, True)
            writePin(COM_CATH2, False)
            writePin(AN2_1200, False)
            writePin(AN1_1200, True)
            writePin(AN_1200, True)
            G_PHASE = False
        else:
            writePin(COM_CATH1, False)
            writePin(COM_CATH2, True)
            writePin(AN2_1200, True)
            writePin(AN1_1200, False)
            writePin(AN_1200, True)
            G_PHASE = True


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
#8/bace/0xd1f/1
