import requests
import json
import os
import time
import random
from dotenv import load_dotenv

load_dotenv()
COMFY_URL = os.getenv("COMFY_URL", "http://127.0.0.1:8001")

def is_comfy_available():
    """Returns True if the local ComfyUI server is reachable."""
    try:
        # Just check if the server is alive by calling /
        response = requests.get(COMFY_URL, timeout=2)
        return True # Any response means the server is reachable
    except:
        return False

def get_comfy_error(job_info):
    """Extracts a human-readable error from ComfyUI history/status."""
    status = job_info.get("status", {})
    messages = status.get("messages", [])
    for msg in messages:
        if isinstance(msg, list) and len(msg) > 1 and msg[0] == "execution_error":
            err_details = msg[1]
            node_id = err_details.get("node_id")
            node_type = err_details.get("node_type")
            exception = err_details.get("exception_message", "Unknown error")
            return f"Node {node_id} ({node_type}) failed: {exception}"
    return "Unknown execution error (check ComfyUI console)"

def generate_cinematic_backgrounds(prompt, count=1, output_dir="assets/comfy_out", width=1024, height=1024):
    """
    Triggers local ComfyUI to generate high-end cinematic backgrounds.
    Supports auto-healing fallback across available checkpoints.
    """
    print(f"[ComfyBridge] Generating {count} AI backgrounds for: {prompt}")
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Fetch available checkpoints to find one that actually exists
    available = []
    try:
        res = requests.get(f"{COMFY_URL}/object_info/CheckpointLoaderSimple", timeout=3)
        if res.status_code == 200:
            available = res.json().get("CheckpointLoaderSimple", {}).get("input", {}).get("required", {}).get("ckpt_name", [[]])[0]
    except Exception as e:
        print(f"[ComfyBridge] Failed to fetch checkpoints list: {e}")
        
    # 2. Build list of preferred checkpoints (order of preference)
    ckpt_list = [
        "DreamShaperXL_Lightning-SFW.safetensors",
        "Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors",
        "dreamshaper_8.safetensors",
        "DreamShaper_8_pruned.safetensors",
        "epicrealismXL_v8Kiss.safetensors",
        "realisticVisionV60B1_v51HyperVAE.safetensors"
    ]
    preferred_ckpts = [c for c in ckpt_list if c in available]
    for c in available:
        if c not in preferred_ckpts and "audio" not in c.lower() and "ace" not in c.lower() and "stable" not in c.lower():
            preferred_ckpts.append(c)
            
    if not preferred_ckpts:
        preferred_ckpts = ["DreamShaperXL_Lightning-SFW.safetensors"] # Fallback if list empty
        
    print(f"[ComfyBridge] Sorted checkpoint preference for image gen: {preferred_ckpts}")
    
    # 3. Try generating with each preferred checkpoint until one succeeds
    for ckpt in preferred_ckpts:
        print(f"[ComfyBridge] Attempting background generation with model: {ckpt}")
        is_sdxl = "xl" in ckpt.lower() or "juggernaut" in ckpt.lower() or "epicrealism" in ckpt.lower()
        
        # Adjust settings based on model architecture
        if is_sdxl:
            w, h = width, height
            steps = 6 if "lightning" in ckpt.lower() or "hyper" in ckpt.lower() else 25
            cfg = 2.0 if "lightning" in ckpt.lower() or "hyper" in ckpt.lower() else 7.0
            sampler = "dpmpp_sde" if "lightning" in ckpt.lower() else "dpmpp_2m"
            scheduler = "karras"
        else:
            w, h = 512, 768 # Standard vertical for SD 1.5
            steps = 8 if "hyper" in ckpt.lower() or "lightning" in ckpt.lower() else 20
            cfg = 1.5 if "hyper" in ckpt.lower() or "lightning" in ckpt.lower() else 7.0
            sampler = "dpmpp_2m"
            scheduler = "karras"
            
        workflow = {
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": random.randint(1, 1000000),
                    "steps": steps,
                    "cfg": cfg,
                    "denoise": 1,
                    "sampler_name": sampler,
                    "scheduler": scheduler,
                    "model": ["4", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["5", 0]
                }
            },
            "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
            "5": {"class_type": "EmptyLatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}},
            "6": {"class_type": "CLIPTextEncode", "inputs": {"text": f"Cinematic, high-impact, 8k, viral style, studio lighting, {prompt}", "clip": ["4", 1]}},
            "7": {"class_type": "CLIPTextEncode", "inputs": {"text": "low quality, text, watermark, blurry, distorted", "clip": ["4", 1]}},
            "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
            "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "comfy_short", "images": ["8", 0]}}
        }
        
        try:
            response = requests.post(f"{COMFY_URL}/prompt", json={"prompt": workflow}, timeout=10)
            if response.status_code != 200:
                print(f"[ComfyBridge] Error: Server returned {response.status_code} for {ckpt}. Trying next...")
                continue
                
            prompt_id = response.json().get("prompt_id")
            print(f"[ComfyBridge] Queued image job: {prompt_id}")
            
            success = False
            # Increased timeout to 120s to allow model caching
            for i in range(60):
                time.sleep(2)
                history_res = requests.get(f"{COMFY_URL}/history/{prompt_id}")
                if history_res.status_code == 200:
                    history = history_res.json()
                    if prompt_id in history:
                        job_info = history[prompt_id]
                        if 'outputs' in job_info and '9' in job_info['outputs']:
                            img_data = job_info['outputs']['9']['images'][0]
                            filename = img_data['filename']
                            subfolder = img_data.get('subfolder', '')
                            
                            view_url = f"{COMFY_URL}/view?filename={filename}&subfolder={subfolder}&type=output"
                            img_res = requests.get(view_url)
                            out_path = os.path.join(output_dir, f"ai_bg_{int(time.time())}.png")
                            with open(out_path, "wb") as f:
                                f.write(img_res.content)
                            print(f"[ComfyBridge] Successfully generated background using {ckpt}: {out_path}")
                            return [out_path]
                        else:
                            error_msg = get_comfy_error(job_info)
                            print(f"[ComfyBridge] Image job failed for {ckpt}: {error_msg}")
                            break # Try next checkpoint
            
            if not success:
                print(f"[ComfyBridge] Generation timed out or failed for {ckpt}. Trying next...")
                
        except Exception as e:
            print(f"[ComfyBridge] Exception with {ckpt}: {e}. Trying next...")
            
    print("[ComfyBridge] All preferred checkpoints failed for background generation.")
    return []

def generate_ai_audio(prompt, duration=15, output_dir="assets/comfy_audio", ckpt_name="ace_step_v1_3.5b.safetensors"):
    """
    [PRO] Generates unique AI music or SFX via ComfyUI (Stable Audio / AudioLDM).
    Uses professional T2A nodes for studio-grade sonic branding.
    """
    print(f"[ComfyBridge] [PRO] Generating {duration}s AI Audio using model '{ckpt_name}' for: {prompt}")
    os.makedirs(output_dir, exist_ok=True)
    
    # Check for user-provided Stable Audio 3.0 workflow template
    custom_workflow_path = "C:\\Users\\win10\\Downloads\\audio_stable_audio_3_medium_base.json"
    if os.path.exists(custom_workflow_path):
        print(f"[ComfyBridge] Found custom Stable Audio 3.0 workflow at: {custom_workflow_path}")
        try:
            with open(custom_workflow_path, "r", encoding="utf-8") as f:
                workflow = json.load(f)
            
            # Inject inputs dynamically based on node IDs in the user's workflow
            if "52:31" in workflow and "inputs" in workflow["52:31"]:
                workflow["52:31"]["inputs"]["value"] = prompt
            if "52:36" in workflow and "inputs" in workflow["52:36"]:
                workflow["52:36"]["inputs"]["value"] = float(duration)
            if "52:35" in workflow and "inputs" in workflow["52:35"]:
                workflow["52:35"]["inputs"]["value"] = False
            if "52:3" in workflow and "inputs" in workflow["52:3"]:
                workflow["52:3"]["inputs"]["seed"] = random.randint(1, 1000000000)
                # Preserve the custom workflow's native sampler, scheduler, and steps settings if present.
                if "sampler_name" not in workflow["52:3"]["inputs"]:
                    workflow["52:3"]["inputs"]["sampler_name"] = "dpmpp_2m"
                if "scheduler" not in workflow["52:3"]["inputs"]:
                    workflow["52:3"]["inputs"]["scheduler"] = "karras"
                if "steps" not in workflow["52:3"]["inputs"]:
                    workflow["52:3"]["inputs"]["steps"] = 50
            if "52:25" in workflow and "inputs" in workflow["52:25"] and ckpt_name:
                workflow["52:25"]["inputs"]["ckpt_name"] = ckpt_name
                
            print("[ComfyBridge] Successfully initialized custom Stable Audio 3.0 workflow template.")
        except Exception as we:
            print(f"[Warning] Failed to parse custom workflow JSON: {we}. Falling back to default workflow.")
            custom_workflow_path = None

    if not os.path.exists(custom_workflow_path or ""):
        # 🟢 DEFAULT CONFIG: Stable Audio / AudioLDM Workflow Template
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
            "11": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt_name}},
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
                    outputs = job_info.get('outputs', {})
                    
                    # Dynamically find the node outputting audio
                    audio_node_id = None
                    for nid, nout in outputs.items():
                        if 'audio' in nout:
                            audio_node_id = nid
                            break
                            
                    if audio_node_id:
                        audio_data = outputs[audio_node_id]['audio'][0]
                        filename = audio_data['filename']
                        subfolder = audio_data.get('subfolder', '')
                        
                        # Download the result
                        view_url = f"{COMFY_URL}/view?filename={filename}&subfolder={subfolder}&type=output"
                        audio_res = requests.get(view_url)
                        out_path = os.path.join(output_dir, f"ai_audio_{int(time.time())}.mp3")
                        with open(out_path, "wb") as f:
                            f.write(audio_res.content)
                        print(f"[ComfyBridge] Successfully generated AI Audio: {out_path}")
                        return out_path
                    else:
                        error_msg = get_comfy_error(job_info)
                        print(f"[ComfyBridge] Audio job failed: {error_msg}")
                        return None
            
            if i % 10 == 0 and i > 0:
                print(f"[ComfyBridge] Still waiting for audio... ({i*2}s elapsed)")
            
        print(f"[ComfyBridge] Audio generation timed out after 240 seconds.")
            
    except Exception as e:
        print(f"[ComfyBridge] Audio generation exception: {e}")
    
    return None

def get_available_checkpoints():
    """Tries to list available checkpoints from ComfyUI CheckpointLoaderSimple node info."""
    try:
        response = requests.get(f"{COMFY_URL}/object_info/CheckpointLoaderSimple")
        if response.status_code == 200:
            info = response.json()
            # The structure for inputs usually lists valid options in a list
            ckpts = info.get("CheckpointLoaderSimple", {}).get("input", {}).get("required", {}).get("ckpt_name", [])
            # It's usually a list where the first element is the list of choices
            if ckpts and isinstance(ckpts[0], list):
                return ckpts[0]
            return ckpts
    except:
        pass
    return []
