import requests
import json
import os
import sys
from engine import comfy_bridge

def diagnose():
    print("=== ComfyUI Diagnostic Tool (Hyper-Verbose) ===")
    print(f"Python Version: {sys.version}")
    print(f"Current Directory: {os.getcwd()}")
    
    # Check if comfy_bridge is seeing the .env
    print(f"\n[Environment check in comfy_bridge]")
    print(f"COMFY_URL set to: {comfy_bridge.COMFY_URL}")
    
    # Try a direct request with its own timeout and error reporting
    print(f"\n[Direct Connection Test]")
    target = comfy_bridge.COMFY_URL
    print(f"Attempting GET {target} ...")
    try:
        r = requests.get(target, timeout=5)
        print(f"[SUCCESS] Received status {r.status_code}")
        if r.status_code == 200:
            print(f"Response (first 100 chars): {r.text[:100]}")
    except Exception as e:
        print(f"[FAILED] Direct request to {target} error: {e}")
        
    # Check if the comfy_bridge helper works
    print(f"\n[Wrapper Test]")
    if comfy_bridge.is_comfy_available():
        print(f"[OK] comfy_bridge.is_comfy_available() returned True")
    else:
        print(f"[FAIL] comfy_bridge.is_comfy_available() returned False")

    # 2. Check Models
    print(f"\n[Models check]")
    try:
        ckpts = comfy_bridge.get_available_checkpoints()
        print(f"Available Checkpoints ({len(ckpts)} found):")
        for c in ckpts:
            print(f"  - {c}")
    except Exception as e:
        print(f"Could not fetch models: {e}")

if __name__ == "__main__":
    diagnose()
