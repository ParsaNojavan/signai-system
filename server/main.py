import sys
import json
import collections
from pathlib import Path
import numpy as np
import cv2
import torch
import torch.nn.functional as F
import mediapipe as mp
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# اضافه کردن مسیر پروژه برای دسترسی به فایل‌های ماژول training
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR / "training"))
from model import SignLanguageBiLSTM

# ==================== پیکربندی ====================
MODEL_PATH = BASE_DIR / "models" / "best_model.pth"
ACTIONS_FILE = BASE_DIR / "dataset" / "actions.json"
SEQUENCE_LENGTH = 30
CONFIDENCE_THRESHOLD = 0.80  # فقط پیش‌بینی‌های بالای 80% معتبرند

app = FastAPI(title="SignAI Inference Server", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== لود مدل و ابزارها ====================
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"⚡ Device سرور: {device}")

# لود مدیاپایپ
mp_holistic = mp.solutions.holistic

# لود ساختار مدل و وزن‌ها
checkpoint = torch.load(MODEL_PATH, map_location=device)
actions = checkpoint.get("actions", [])
input_size = checkpoint["input_size"]
hidden_size = checkpoint["hidden_size"]
num_layers = checkpoint["num_layers"]
num_classes = checkpoint["num_classes"]

model = SignLanguageBiLSTM(
    input_size=input_size,
    hidden_size=hidden_size,
    num_layers=num_layers,
    num_classes=num_classes
).to(device)
model.load_state_dict(checkpoint["model_state_dict"])
model.eval()
print(f"✅ مدل با موفقیت لود شد. کلاس‌ها: {actions} | سایز ورودی: {input_size}")

# ==================== توابع کمکی پردازش فریم ====================
def extract_keypoints(results) -> np.ndarray:
    """
    استخراج دقیق ۲۱۸ ویژگی منطبق بر مرحله جمع‌آوری داده:
    - بالاتنه: ۲۳ نقطه اول Pose با مختصات (x, y, z, visibility) -> ۹۲ ویژگی
    - دست چپ: ۲۱ نقطه با مختصات (x, y, z) -> ۶۳ ویژگی
    - دست راست: ۲۱ نقطه با مختصات (x, y, z) -> ۶۳ ویژگی
    مجموع = ۲۱۸ ویژگی
    """
    # بالاتنه (Pose landmarks 0 تا 22 -> 23 نقطه * 4 = 92)
    if results.pose_landmarks:
        pose = np.array(
            [[res.x, res.y, res.z, res.visibility] for res in results.pose_landmarks.landmark[:23]]
        ).flatten()
    else:
        pose = np.zeros(23 * 4)

    # دست چپ (21 نقطه * 3 = 63)
    if results.left_hand_landmarks:
        lh = np.array(
            [[res.x, res.y, res.z] for res in results.left_hand_landmarks.landmark]
        ).flatten()
    else:
        lh = np.zeros(21 * 3)

    # دست راست (21 نقطه * 3 = 63)
    if results.right_hand_landmarks:
        rh = np.array(
            [[res.x, res.y, res.z] for res in results.right_hand_landmarks.landmark]
        ).flatten()
    else:
        rh = np.zeros(21 * 3)

    # مجموع دقیقاً ۲۱۸
    return np.concatenate([pose, lh, rh])

# ==================== Endpoints ====================
@app.get("/health")
async def health_check():
    return {
        "status": "online",
        "device": str(device),
        "classes": actions,
        "sequence_length": SEQUENCE_LENGTH
    }

@app.websocket("/ws/inference")
async def websocket_inference(websocket: WebSocket):
    await websocket.accept()
    print("🔌 کلاینت متصل شد.")
    
    # بافر برای نگه‌داری ۳۰ فریم متوالی
    sequence_buffer = collections.deque(maxlen=SEQUENCE_LENGTH)
    
    with mp_holistic.Holistic(
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
        model_complexity=1
    ) as holistic:
        try:
            while True:
                # دریافت داده تصویری به عنوان بایت (JPEG frame)
                data = await websocket.receive_bytes()
                
                # تبدیل بایت‌ها به فریم OpenCV
                nparr = np.frombuffer(data, np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if frame is None:
                    continue

                # پردازش مدیاپایپ
                image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                image_rgb.flags.writeable = False
                results = holistic.process(image_rgb)
                
                # استخراج ۲۱۸ ویژگی هماهنگ با مدل
                keypoints = extract_keypoints(results)
                sequence_buffer.append(keypoints)

                response = {
                    "action": "idle",
                    "confidence": 0.0,
                    "ready": False
                }

                # وقتی ۳۰ فریم کامل شد استنتاج را اجرا می‌کنیم
                if len(sequence_buffer) == SEQUENCE_LENGTH:
                    input_tensor = torch.tensor(
                        np.expand_dims(list(sequence_buffer), axis=0),
                        dtype=torch.float32
                    ).to(device)

                    with torch.no_grad():
                        logits = model(input_tensor)
                        probs = F.softmax(logits, dim=1)
                        confidence, predicted_idx = torch.max(probs, dim=1)
                        
                        conf_val = confidence.item()
                        pred_class = actions[predicted_idx.item()]
                        
                        if conf_val >= CONFIDENCE_THRESHOLD:
                            response["action"] = pred_class
                            response["confidence"] = round(conf_val, 3)
                        else:
                            response["action"] = "uncertain"
                            response["confidence"] = round(conf_val, 3)
                            
                        response["ready"] = True

                await websocket.send_json(response)

        except WebSocketDisconnect:
            print("❌ ارتباط کلاینت قطع شد.")
        except Exception as e:
            print(f"⚠️ خطا در پایپ‌لاین استنتاج: {e}")
            await websocket.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
