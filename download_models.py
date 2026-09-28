import os
import shutil
import urllib.request
import zipfile

url = 'https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-windows.zip'
zip_path = r'C:\Users\win10\Downloads\upscale\full_models.zip'
target_dir = r'C:\Users\win10\Downloads\upscale\realesrgan-ncnn-vulkan-v0.2.0-windows\models'
temp_extract = r'C:\Users\win10\Downloads\upscale\temp_extract'

print("[Log] Downloading official Real-ESRGAN AI model weights pack...")
urllib.request.urlretrieve(url, zip_path)

print("[Log] Extracting model weights...")
with zipfile.ZipFile(zip_path, 'r') as z:
    z.extractall(temp_extract)

os.makedirs(target_dir, exist_ok=True)
extracted_models = os.path.join(temp_extract, 'realesrgan-ncnn-vulkan-20220424-windows', 'models')

for f in os.listdir(extracted_models):
    shutil.copy2(os.path.join(extracted_models, f), os.path.join(target_dir, f))

print(f"[SUCCESS] Downloaded and installed {len(os.listdir(target_dir))} AI model files into:")
print(f"  {target_dir}")
print("Available models:", os.listdir(target_dir))

# Clean up
if os.path.exists(zip_path): os.remove(zip_path)
if os.path.exists(temp_extract): shutil.rmtree(temp_extract)
