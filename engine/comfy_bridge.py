import requests
import json
import os
import time
import random

COMFY_URL = os.getenv("COMFY_URL", "http://127.0.0.1:8000")

def is_comfy_available():
    """Returns True if the local ComfyUI server is reachable."""
    try:
        response = requests.get(f"{COMFY_URL}/system_stats", timeout=2)
        return response.status_code == 200
    except:
        return False

def generate_cinematic_backgrounds(prompt, count=5, output_dir="assets/comfy_out"):
    """
    Triggers local ComfyUI to generate high-end cinematic backgrounds.
    Uses SDXL-Lightning for 1M-sub quality in under 5 seconds.
    """
    print(f"[ComfyBridge] Generating {count} AI backgrounds for: {prompt}")
    os.makedirs(output_dir, exist_ok=True)
    
    # 🟢 PRO CONFIG: Optimized for RTX 4060 (Lightning XL)
    workflow = {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": random.randint(1, 1000000),
                "steps": 6,
                "cfg": 2.0,
                "denoise": 1,
                "sampler_name": "dpmpp_sde",
                "scheduler": "karras",
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0]
            }
        },
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "DreamShaperXL_Lightning-SFW.safetensors"}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 1024, "height": 1024, "batch_size": 1}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": f"Cinematic, high-impact, 8k, viral thumbnail style, {prompt}", "clip": ["4", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": "low quality, text, watermark, blurry, distorted", "clip": ["4", 1]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "comfy_short", "images": ["8", 0]}}
    }

    try:
        response = requests.post(f"{COMFY_URL}/prompt", json={"prompt": workflow}, timeout=10)
        if response.status_code != 200:
            print(f"[ComfyBridge] Error: Server returned status {response.status_code}: {response.text}")
            return []
        
        prompt_id = response.json().get("prompt_id")
        print(f"[ComfyBridge] Queued image job: {prompt_id}")
        
        # Simple polling for results
        for i in range(60): # 60 second timeout
            history_res = requests.get(f"{COMFY_URL}/history/{prompt_id}")
            if history_res.status_code == 200:
                history = history_res.json()
                if prompt_id in history:
                    # Job complete!
                    job_info = history[prompt_id]
                    if 'outputs' in job_info and '9' in job_info['outputs']:
                        img_data = job_info['outputs']['9']['images'][0]
                        filename = img_data['filename']
                        
                        # Download the result
                        img_res = requests.get(f"{COMFY_URL}/view?filename={filename}&type=output")
                        out_path = os.path.join(output_dir, f"ai_bg_{int(time.time())}.png")
                        with open(out_path, "wb") as f:
                            f.write(img_res.content)
                        return [out_path] 
                    else:
                        print(f"[ComfyBridge] Image job finished but '9' output was missing. History: {job_info}")
                        return []
            time.sleep(1)
            
        print(f"[ComfyBridge] Image generation timed out after 60 seconds.")
            
    except requests.exceptions.RequestException as e:
        print(f"[ComfyBridge] Connection failed: {e}. Ensure ComfyUI is running on {COMFY_URL}")
    except Exception as e:
        print(f"[ComfyBridge] Exception during image generation: {e}")
    
    return []

def generate_ai_audio(prompt, duration=15, output_dir="assets/comfy_audio"):
    """
    [PRO] Generates unique AI music or SFX via ComfyUI (Stable Audio / AudioLDM).
    Uses professional T2A nodes for studio-grade sonic branding.
    """
    print(f"[ComfyBridge] [PRO] Generating {duration}s AI Audio for: {prompt}")
    os.makedirs(output_dir, exist_ok=True)
    
    # 🟢 PRO CONFIG: Stable Audio / AudioLDM Workflow Template
    workflow = {
        "10": {
            "class_type": "StableAudioSampler",
            "inputs": {
                "seed": random.randint(1, 1000000),
                "steps": 50,
                "cfg": 7.0,
                "sampler_name": "dpmpp_2m",
                "scheduler": "karras",
                "model": ["11", 0],
                "positive": ["12", 0],
                "seconds_total": duration
            }
        },
        "11": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "audio_ace_step_1_t2a_song.safetensors"}},
        "12": {"class_type": "CLIPTextEncode", "inputs": {"text": f"High quality, studio recorded, cinematic, {prompt}", "clip": ["11", 1]}},
        "13": {"class_type": "SaveAudio", "inputs": {"filename_prefix": "comfy_audio", "audio": ["10", 0]}}
    }

    try:
        response = requests.post(f"{COMFY_URL}/prompt", json={"prompt": workflow}, timeout=10)
        if response.status_code != 200:
            print(f"[ComfyBridge] Error: Server returned status {response.status_code}: {response.text}")
            return None
        
        prompt_id = response.json().get("prompt_id")
        print(f"[ComfyBridge] Audio job submitted (ID: {prompt_id}). Polling for result...")
        
        # Polling for audio result
        for i in range(120): # Audio takes longer (approx 2 mins timeout)
            time.sleep(2)
            history_res = requests.get(f"{COMFY_URL}/history/{prompt_id}")
            if history_res.status_code == 200:
                history = history_res.json()
                if prompt_id in history:
                    # Job complete!
                    job_info = history[prompt_id]
                    if 'outputs' in job_info and '13' in job_info['outputs']:
                        audio_data = job_info['outputs']['13']['audio'][0]
                        filename = audio_data['filename']
                        
                        # Download the result
                        audio_res = requests.get(f"{COMFY_URL}/view?filename={filename}&type=output")
                        out_path = os.path.join(output_dir, f"ai_audio_{int(time.time())}.mp3")
                        with open(out_path, "wb") as f:
                            f.write(audio_res.content)
                        print(f"[ComfyBridge] Successfully generated AI Audio: {out_path}")
                        return out_path
                    else:
                        print(f"[ComfyBridge] Audio job finished but '13' output was missing. History: {job_info}")
                        return None
            
            if i % 10 == 0 and i > 0:
                print(f"[ComfyBridge] Still waiting for audio... ({i*2}s elapsed)")
            
        print(f"[ComfyBridge] Audio generation timed out after 240 seconds.")
            
    except Exception as e:
        print(f"[ComfyBridge] Audio generation exception: {e}")
    
    return None
