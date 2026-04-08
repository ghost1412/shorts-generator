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

def run_generation(mode, category, script, vibe, video_id, user_id, style=None, source_video=None, use_audio_detect=False, user_context=None, style_context=None):
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
    
    # Start the processing in a background thread so the HTTP request returns immediately
    thread = threading.Thread(target=run_generation, args=(mode, category, script, vibe, video_id, user_id, style, source_video, use_audio_detect, user_context, style_context))
    thread.start()
    
    return jsonify({
        "success": True, 
        "message": "Render started in background",
        "job_id": video_id
    }), 202

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ready"}), 200

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print(f"--- ShortsFlow Dedicated Worker listening on port {port} ---")
    app.run(host='0.0.0.0', port=port)
