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

# ==================== پیکربندی مسیرها ====================
BASE_DIR = Path(__file__).resolve().parent.parent if Path(__file__).resolve().parent.name in ["server", "api"] else Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "training"))
from model import SignLanguageBiLSTM

MODEL_PATH = BASE_DIR / "models" / "best_model.pth"
ACTIONS_FILE = BASE_DIR / "dataset" / "actions.json"
SEQUENCE_LENGTH = 30
CONFIDENCE_THRESHOLD = 0.75  # آستانه اطمینان قابل قبول
MARGIN_THRESHOLD = 0.15      # اختلاف با کلاس دوم برای رد تردید

app = FastAPI(title="SignAI Production Server", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== لود مدل و چک‌پوینت ====================
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"⚡ Device سرور: {device}")

# لود لیست کلمات
if ACTIONS_FILE.exists():
    with open(ACTIONS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        actions = data["actions"] if isinstance(data, dict) and "actions" in data else data
else:
    actions = []

checkpoint = torch.load(MODEL_PATH, map_location=device)
if not actions and "actions" in checkpoint:
    actions = checkpoint["actions"]

input_size = checkpoint.get("input_size", 218)
hidden_size = checkpoint.get("hidden_size", 128)
num_layers = checkpoint.get("num_layers", 2)
num_classes = checkpoint.get("num_classes", len(actions))

model = SignLanguageBiLSTM(
    input_size=input_size,
    hidden_size=hidden_size,
    num_layers=num_layers,
    num_classes=num_classes,
    dropout=0.3
).to(device)

model.load_state_dict(checkpoint["model_state_dict"])
model.eval()
print(f"✅ مدل لود شد | کلاس‌ها ({len(actions)}): {actions} | سایز ویژگی: {input_size}")

# لود MediaPipe
mp_holistic = mp.solutions.holistic

# ==================== توابع استخراج ویژگی و نرمال‌سازی ====================
def extract_keypoints(results) -> np.ndarray:
    """
    استخراج دقیق ۲۱۸ ویژگی کاملاً منطبق بر پایپ‌لاین آموزش:
    - انتقال مختصات نسبت به نقطه وسط دو شانه
    - مقیاس‌بندی بر اساس فاصله دو شانه و مچ تا کف دست
    - اصلاح چرخش زاویه شانه
    """
    # 1. Pose (بالاتنه - ۲۳ نقطه اول: ۹۲ ویژگی)
    if results.pose_landmarks:
        pose_raw = results.pose_landmarks.landmark
        left_shoulder = np.array([pose_raw[11].x, pose_raw[11].y, pose_raw[11].z])
        right_shoulder = np.array([pose_raw[12].x, pose_raw[12].y, pose_raw[12].z])
        mid_shoulder = (left_shoulder + right_shoulder) / 2.0
        shoulder_dist = np.linalg.norm(left_shoulder - right_shoulder)
        scale = shoulder_dist if shoulder_dist > 1e-4 else 1.0
        
        dx, dy = right_shoulder[0] - left_shoulder[0], right_shoulder[1] - left_shoulder[1]
        angle = -np.arctan2(dy, dx)
        rot_matrix = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])

        pose_list = []
        for i in range(23):
            lm = pose_raw[i]
            coord = np.array([lm.x, lm.y, lm.z])
            norm_coord = (coord - mid_shoulder) / scale
            xy_rot = np.dot(rot_matrix, norm_coord[:2])
            pose_list.extend([xy_rot[0], xy_rot[1], norm_coord[2], lm.visibility])
        pose_feat = np.array(pose_list)
    else:
        pose_feat = np.zeros(23 * 4)

    # 2. Left Hand (۶۳ ویژگی)
    if results.left_hand_landmarks:
        lh_raw = results.left_hand_landmarks.landmark
        wrist = np.array([lh_raw[0].x, lh_raw[0].y, lh_raw[0].z])
        hand_scale = np.linalg.norm(np.array([lh_raw[9].x, lh_raw[9].y, lh_raw[9].z]) - wrist)
        hand_scale = hand_scale if hand_scale > 1e-4 else 1.0
        lh_feat = np.array([((np.array([lm.x, lm.y, lm.z]) - wrist) / hand_scale) for lm in lh_raw]).flatten()
    else:
        lh_feat = np.zeros(21 * 3)

    # 3. Right Hand (۶۳ ویژگی)
    if results.right_hand_landmarks:
        rh_raw = results.right_hand_landmarks.landmark
        wrist = np.array([rh_raw[0].x, rh_raw[0].y, rh_raw[0].z])
        hand_scale = np.linalg.norm(np.array([rh_raw[9].x, rh_raw[9].y, rh_raw[9].z]) - wrist)
        hand_scale = hand_scale if hand_scale > 1e-4 else 1.0
        rh_feat = np.array([((np.array([lm.x, lm.y, lm.z]) - wrist) / hand_scale) for lm in rh_raw]).flatten()
    else:
        rh_feat = np.zeros(21 * 3)

    return np.concatenate([pose_feat, lh_feat, rh_feat])

def mirror_keypoints(kp: np.ndarray) -> np.ndarray:
    """قرینه‌سازی بردار ویژگی برای پشتیبانی همزمان از افراد راست‌دست و چپ‌دست"""
    mirrored = kp.copy()
    for i in range(23):
        mirrored[i * 4] = -mirrored[i * 4]
        
    pose_part = mirrored[:92]
    lh_part = mirrored[92:92+63]
    rh_part = mirrored[92+63:]
    
    for i in range(21):
        if np.any(lh_part):
            lh_part[i * 3] = -lh_part[i * 3]
        if np.any(rh_part):
            rh_part[i * 3] = -rh_part[i * 3]

    return np.concatenate([pose_part, rh_part, lh_part])

def check_hand_activity(results) -> bool:
    """گارد هوشمند: اگر دست بالا نیامده باشد یا پنهان باشد، فاز IDLE است"""
    lh_vis = results.left_hand_landmarks is not None
    rh_vis = results.right_hand_landmarks is not None
    
    if not (lh_vis or rh_vis):
        return False
        
    if results.pose_landmarks:
        pose = results.pose_landmarks.landmark
        shoulder_y = (pose[11].y + pose[12].y) / 2.0
        # بررسی ارتفاع مچ دست‌ها نسبت به شانه
        if lh_vis and results.left_hand_landmarks.landmark[0].y < (shoulder_y + 0.35):
            return True
        if rh_vis and results.right_hand_landmarks.landmark[0].y < (shoulder_y + 0.35):
            return True
            
    return False

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
    print("🔌 کلاینت به WebSocket استنتاج متصل شد.")
    
    sequence_buffer = collections.deque(maxlen=SEQUENCE_LENGTH)
    
    with mp_holistic.Holistic(
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
        model_complexity=1
    ) as holistic:
        try:
            while True:
                data = await websocket.receive_bytes()
                nparr = np.frombuffer(data, np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if frame is None:
                    continue

                image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                image_rgb.flags.writeable = False
                results = holistic.process(image_rgb)
                
                # بررسی فعالیت دست (گارد IDLE)
                hand_active = check_hand_activity(results)
                
                response = {
                    "action": "idle",
                    "confidence": 0.0,
                    "hand_mode": "none",
                    "ready": False
                }

                if not hand_active:
                    sequence_buffer.clear()
                    await websocket.send_json(response)
                    continue

                # استخراج ویژگی نرمال‌شده
                keypoints = extract_keypoints(results)
                sequence_buffer.append(keypoints)

                if len(sequence_buffer) == SEQUENCE_LENGTH:
                    seq_arr = np.array(sequence_buffer)
                    
                    # استنتاج دوگانه (دست اصلی + دست قرینه)
                    tensor_orig = torch.tensor(seq_arr, dtype=torch.float32).unsqueeze(0).to(device)
                    seq_mirrored = np.array([mirror_keypoints(kp) for kp in seq_arr])
                    tensor_mirr = torch.tensor(seq_mirrored, dtype=torch.float32).unsqueeze(0).to(device)

                    with torch.no_grad():
                        probs_orig = F.softmax(model(tensor_orig), dim=1)[0]
                        probs_mirr = F.softmax(model(tensor_mirr), dim=1)[0]
                        
                        top_conf_orig, top_idx_orig = torch.topk(probs_orig, 2)
                        top_conf_mirr, top_idx_mirr = torch.topk(probs_mirr, 2)

                    # انتخاب شاخه‌ای که اطمینان بیشتری دارد
                    if top_conf_mirr[0] > top_conf_orig[0]:
                        best_conf = top_conf_mirr[0].item()
                        best_idx = top_idx_mirr[0].item()
                        margin = (top_conf_mirr[0] - top_conf_mirr[1]).item()
                        hand_mode = "mirrored"
                    else:
                        best_conf = top_conf_orig[0].item()
                        best_idx = top_idx_orig[0].item()
                        margin = (top_conf_orig[0] - top_conf_orig[1]).item()
                        hand_mode = "original"

                    # بررسی Margin و Threshold برای جلوگیری از تشخیص غلط کلمات مشابه
                    if best_conf >= CONFIDENCE_THRESHOLD and margin >= MARGIN_THRESHOLD:
                        response["action"] = actions[best_idx]
                        response["confidence"] = round(best_conf, 3)
                    else:
                        response["action"] = "uncertain"
                        response["confidence"] = round(best_conf, 3)

                    response["hand_mode"] = hand_mode
                    response["ready"] = True

                await websocket.send_json(response)

        except WebSocketDisconnect:
            print("❌ ارتباط کلاینت قطع شد.")
        except Exception as e:
            print(f"⚠️ خطا در پردازش WebSocket: {e}")
            try:
                await websocket.close()
            except:
                pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
