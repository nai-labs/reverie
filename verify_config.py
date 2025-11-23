import os
from dotenv import load_dotenv
import config

print("--- Config Verification ---")
print(f"INSIGHTFACE_MODEL_PATH: {config.INSIGHTFACE_MODEL_PATH}")
print(f"STABLE_DIFFUSION_URL: {config.STABLE_DIFFUSION_URL}")
print(f"LMSTUDIO_URL: {config.LMSTUDIO_URL}")
print(f"ZONOS_URL: {config.ZONOS_URL}")

# Check if they match expected defaults if env vars are missing
if config.INSIGHTFACE_MODEL_PATH == './models/insightface/inswapper_128.onnx':
    print("SUCCESS: INSIGHTFACE_MODEL_PATH matches default.")
else:
    print("INFO: INSIGHTFACE_MODEL_PATH is set from env.")

if config.STABLE_DIFFUSION_URL == 'http://127.0.0.1:7860/sdapi/v1/txt2img':
    print("SUCCESS: STABLE_DIFFUSION_URL matches default.")
else:
    print("INFO: STABLE_DIFFUSION_URL is set from env.")
