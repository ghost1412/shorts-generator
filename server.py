from flask import Flask, request, jsonify
import subprocess
import os
import threading
import uuid
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# This is a basic worker server that listens for render requests from the Next.js dashboard.
# It runs the python main.py command in the background.

def run_generation(mode, category, script, vibe, video_id, user_id, style=None, source_video=None, use_audio_detect=False, user_context=None, style_context=None, prompt=None, ckpt_name=None):
    """Executes the main.py script as a separate process."""
    cmd = [
        "python", "main.py", 
        "--mode", mode, 
        "--vibe", vibe,
        "--video_id", video_id,
        "--user_id", user_id
    ]
    
    if style:
        cmd.extend(["--style", style])
    if source_video:
        cmd.extend(["--source_video", source_video])
    if use_audio_detect:
        cmd.append("--use_audio_detect")
    if user_context:
        cmd.extend(["--user_context", user_context])
    if style_context:
        cmd.extend(["--style_context", style_context])
    if prompt:
        cmd.extend(["--prompt", prompt])
    if ckpt_name:
        cmd.extend(["--ckpt_name", ckpt_name])
    
    if category:
        cmd.extend(["--category", category])
    if script:
        cmd.extend(["--script", script])
        
    print(f"[Log] Starting Render Job [{video_id}]: {' '.join(cmd)}")
    
    try:
        # Run the command and capture output with UTF-8 encoding
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        
        if result.returncode == 0:
            print(f"[Log] Render Job [{video_id}] Completed Successfully.")
            # In a real setup, you would call the Next.js webhook here to report success
            # Example: requests.post(WEBHOOK_URL, json={...})
        else:
            print(f"[Error] Render Job [{video_id}] Failed.")
            print(f"Error detail: {result.stderr}")
            
    except Exception as e:
        print(f"[Critical] Error in worker thread: {str(e)}")

@app.route('/render', methods=['POST'])
def trigger_render():
    data = request.json
    mode = data.get('mode', 'AUTO')
    category = data.get('category', 'random')
    script = data.get('customScript', '')
    vibe = data.get('vibe', 'suspense')
    user_id = data.get('userId', '')
    video_id = data.get('video_id', str(uuid.uuid4()))
    style = data.get('style')
    source_video = data.get('sourceVideoUrl') # The dashboard sends this for extraction
    use_audio_detect = data.get('useAudioDetect', False)
    user_context = data.get('userContext')
    style_context = data.get('styleContext')
    prompt = data.get('prompt')
    ckpt_name = data.get('ckptName')
    
    # Start the processing in a background thread so the HTTP request returns immediately
    thread = threading.Thread(target=run_generation, args=(mode, category, script, vibe, video_id, user_id, style, source_video, use_audio_detect, user_context, style_context, prompt, ckpt_name))
    thread.start()
    
    return jsonify({
        "success": True, 
        "message": "Render started in background",
        "job_id": video_id
    }), 202

@app.route('/kids-image', methods=['POST'])
def generate_kids_illustration():
    try:
        data = request.json or {}
        prompt = data.get('prompt')
        if not prompt:
            return jsonify({"error": "Prompt is required"}), 400
        
        output_dir = os.path.join("web", "public", "kids_generated")
        os.makedirs(output_dir, exist_ok=True)
        
        from engine.comfy_bridge import generate_cinematic_backgrounds
        # Prepend styling tags for whimsical Pixar style
        full_prompt = f"Whimsical Pixar style 3D render, claymation, cute colorful cartoon illustration for children, vibrant colors, clean details, {prompt}"
        bg_images = generate_cinematic_backgrounds(full_prompt, count=1, output_dir=output_dir, width=768, height=768)
        
        if bg_images and len(bg_images) > 0:
            filename = os.path.basename(bg_images[0])
            relative_path = f"/kids_generated/{filename}"
            return jsonify({
                "success": True,
                "imageUrl": relative_path
            })
        else:
            return jsonify({"error": "Image generation failed"}), 500
    except Exception as e:
        print(f"[Error] Failed to generate kids illustration: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ready"}), 200

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print(f"--- ShortsFlow Dedicated Worker listening on port {port} ---")
    app.run(host='0.0.0.0', port=port)
