GPIO_5 = 20
TX_EN = GPIO_5

@setHook(HOOK_STARTUP)
def on_startup():
    # Default state of TX_EN is low
    setPinDir(TX_EN, True)
    writePin(TX_EN, False)
