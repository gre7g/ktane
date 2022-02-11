# Constants:
ADDRS = "\x07\xaf\xa4\x07\x9f\x1b"

# Globals:
G_SEQ = 0


def lights_off():
    global G_SEQ
    
    dmcastRpc(ADDRS, 1, 3, 0, "s0", G_SEQ, 0)
    G_SEQ += 1
    
    
def lights_on():
    global G_SEQ
    
    dmcastRpc(ADDRS, 1, 3, 0, "s0", G_SEQ, 255)
    G_SEQ += 1
