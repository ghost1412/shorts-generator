import requests
from engine import comfy_bridge

def list_ckpts():
    ckpts = comfy_bridge.get_available_checkpoints()
    print("ALL_CKPTS:")
    for c in ckpts:
        print(f"|{c}|")

if __name__ == "__main__":
    list_ckpts()
