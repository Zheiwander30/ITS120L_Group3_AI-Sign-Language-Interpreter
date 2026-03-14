import os
import cv2
import numpy as np
import mediapipe as mp
import tensorflow as tf
import pickle
from pathlib import Path
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from database import engine, SessionLocal
import models
from routers import users, sessions, payments, autocomplete, vocabulary
from dotenv import load_dotenv

load_dotenv() # Load variables immediately

# 1. Setup Database
models.Base.metadata.create_all(bind=engine)

# 2. App & CORS
app = FastAPI(title="KamAI API")

_ALLOWED_ORIGINS = [
    "http://localhost:5173",   # Vite dev server
    "http://localhost:4173",   # Vite preview
    "http://127.0.0.1:5173",
    os.getenv("FRONTEND_URL", ""),   # production URL from .env
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in _ALLOWED_ORIGINS if o],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Static Files
# Ensures uploads folder exists inside the backend directory
Path("uploads/avatars").mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# 4. Routers
app.include_router(users.router)
app.include_router(sessions.router)
app.include_router(payments.router)
app.include_router(autocomplete.router)
app.include_router(vocabulary.router)

# 5. Load AI Model & Landmark Tools (PATH-PROOF VERSION)
# This finds the directory where main.py actually sits (/app/backend)
BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "models" / "asl_landmark_model.h5"
ENCODER_PATH = BASE_DIR / "models" / "label_encoder.pkl"

# Convert to string for TensorFlow/Pickle compatibility
model_path_str = str(MODEL_PATH)
encoder_path_str = str(ENCODER_PATH)

print(f"--- SERVER STARTUP DEBUG ---")
print(f"BASE_DIR identified as: {BASE_DIR}")
print(f"Looking for model at: {model_path_str}")

# Check if file exists before loading to give a clear error in logs
if not MODEL_PATH.exists():
    print(f"ERROR: Model file not found! List of files in {BASE_DIR}: {os.listdir(BASE_DIR)}")
    # If this fails, the file didn't make it to GitHub or was ignored
    raise FileNotFoundError(f"Missing model file at {model_path_str}")
else:
    print(f"SUCCESS: Model file found. Proceeding to load...")

model = tf.keras.models.load_model(model_path_str)
with open(encoder_path_str, "rb") as f:
    label_encoder = pickle.load(f)

mp_hands = mp.solutions.hands
hands = mp_hands.Hands(static_image_mode=True, max_num_hands=1, min_detection_confidence=0.3)

@app.get("/")
def root():
    return {"status": "KamAI API is running with Landmark AI"}

# Confidence gate for AI predictions
CONFIDENCE_THRESHOLD = 0.75 

@app.post("/predict/")
async def predict(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        results = hands.process(img_rgb)
        
        if not results.multi_hand_landmarks:
            return {"letter": "None", "confidence": 0.0}

        # --- NORMALIZATION LOGIC ---
        hand_landmarks = results.multi_hand_landmarks[0]
        wrist = hand_landmarks.landmark[0]
        
        landmark_list = []
        for lm in hand_landmarks.landmark:
            # Subtract wrist to keep input format identical to training data
            landmark_list.extend([lm.x - wrist.x, lm.y - wrist.y, lm.z - wrist.z])
        
        input_data = np.array([landmark_list], dtype=np.float32)
        prediction = model.predict(input_data, verbose=0)
        
        confidence = float(np.max(prediction))
        if confidence < CONFIDENCE_THRESHOLD:
            return {"letter": "None", "confidence": confidence}

        predicted_idx = np.argmax(prediction)
        predicted_letter = label_encoder.inverse_transform([predicted_idx])[0]
        
        return {"letter": str(predicted_letter), "confidence": round(confidence, 2)}

    except Exception as e:
        return {"letter": "None", "details": str(e)}

# ── Migration: fix vocab_words.tier ENUM column ───────────────────────────────
def _migrate_vocab_tiers():
    from sqlalchemy import text, inspect
    try:
        with engine.begin() as conn:
            inspector = inspect(engine)
            if "vocab_words" not in inspector.get_table_names():
                return

            conn.execute(text(
                "ALTER TABLE vocab_words MODIFY COLUMN tier VARCHAR(32) NOT NULL DEFAULT 'p3'"
            ))

            OLD_TO_NEW = {"free": "p3", "professional": "p2", "enterprise": "p1"}
            for old_val, new_val in OLD_TO_NEW.items():
                conn.execute(text(
                    "UPDATE vocab_words SET tier = :new WHERE tier = :old"
                ), {"new": new_val, "old": old_val})

            conn.execute(text(
                "ALTER TABLE vocab_words MODIFY COLUMN tier ENUM('p1','p2','p3') NOT NULL DEFAULT 'p3'"
            ))

            print("[vocab migration] tier column migrated to ENUM('p1','p2','p3') ✓")
    except Exception as e:
        print(f"[vocab migration] {e}")

_migrate_vocab_tiers()
