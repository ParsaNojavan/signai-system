import os
import time
from pathlib import Path
import cv2
import numpy as np
import mediapipe as mp
from utils import load_actions

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = BASE_DIR / "dataset" / "actions.json"
DATA_PATH = BASE_DIR / "dataset" / "MP_Data"

ACTIONS = load_actions(CONFIG_FILE)
NO_SEQUENCES = 30
SEQUENCE_LENGTH = 30

print(f"✅ کلمات بارگذاری‌شده ({len(ACTIONS)} کلاس): {list(ACTIONS)}")

# ==================== ابزارهای MediaPipe ====================
mp_holistic = mp.solutions.holistic
mp_drawing = mp.solutions.drawing_utils

def extract_keypoints(results) -> np.ndarray:
    # 1. Pose
    if results.pose_landmarks:
        pose_raw = np.array([[lm.x, lm.y, lm.z, lm.visibility] for lm in results.pose_landmarks.landmark[:23]])
        
        left_shoulder = pose_raw[11, :3]
        right_shoulder = pose_raw[12, :3]
        mid_shoulder = (left_shoulder + right_shoulder) / 2.0
        
        body_scale = np.linalg.norm(left_shoulder - right_shoulder)
        if body_scale < 1e-4:
            body_scale = 1.0

        pose_norm = pose_raw.copy()
        pose_norm[:, :3] -= mid_shoulder
        pose_norm[:, :3] /= body_scale
        
        # Tilt correction
        angle = np.arctan2(right_shoulder[1] - left_shoulder[1], right_shoulder[0] - left_shoulder[0])
        cos_a, sin_a = np.cos(-angle), np.sin(-angle)
        x = pose_norm[:, 0].copy()
        y = pose_norm[:, 1].copy()
        pose_norm[:, 0] = cos_a * x - sin_a * y
        pose_norm[:, 1] = sin_a * x + cos_a * y
        
        pose_feat = pose_norm.flatten()
    else:
        pose_feat = np.zeros(23 * 4)

    # 2. Hands
    def normalize_hand(hand_landmarks):
        if not hand_landmarks:
            return np.zeros(21 * 3)
        pts = np.array([[lm.x, lm.y, lm.z] for lm in hand_landmarks.landmark])
        wrist = pts[0]
        pts_rel = pts - wrist
        hand_scale = np.linalg.norm(pts[9] - wrist)
        if hand_scale < 1e-4:
            hand_scale = 1.0
        pts_rel /= hand_scale
        return pts_rel.flatten()

    lh_feat = normalize_hand(results.left_hand_landmarks)
    rh_feat = normalize_hand(results.right_hand_landmarks)

    return np.concatenate([pose_feat, lh_feat, rh_feat])

# ==================== ساخت فولدرها ====================
for action in ACTIONS:
    for sequence in range(NO_SEQUENCES):
        os.makedirs(os.path.join(DATA_PATH, action, str(sequence)), exist_ok=True)

# ==================== راه‌اندازی دوربین ====================
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

with mp_holistic.Holistic(
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
    model_complexity=1  # 1 برای سرعت خوب، اگر فریم ریت بالاست می‌توانی 2 بگذاری
) as holistic:

    for action in ACTIONS:
        for sequence in range(NO_SEQUENCES):
            
            # --- آماده‌سازی قبل از ضبط هر ویدیو (مکث بدون فیریز شدن دوربین) ---
            start_wait = time.time()
            while time.time() - start_wait < 1.2:
                ret, frame = cap.read()
                if not ret: break
                
                countdown = max(0, 1.2 - (time.time() - start_wait))
                cv2.putText(frame, f'READY... {countdown:.1f}s', (160, 200),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 255), 3, cv2.LINE_AA)
                cv2.putText(frame, f'Action: {action} (#{sequence + 1}/{NO_SEQUENCES})', (20, 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 200, 0), 2, cv2.LINE_AA)
                cv2.imshow('SignAI Collector', frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    cap.release()
                    cv2.destroyAllWindows()
                    exit()

            # --- ضبط فریم‌های توالی ---
            for frame_num in range(SEQUENCE_LENGTH):
                ret, frame = cap.read()
                if not ret: break

                image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                image.flags.writeable = False
                results = holistic.process(image)
                image.flags.writeable = True
                image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

                # رسم لندمارک‌ها
                mp_drawing.draw_landmarks(image, results.pose_landmarks, mp_holistic.POSE_CONNECTIONS)
                mp_drawing.draw_landmarks(image, results.left_hand_landmarks, mp_holistic.HAND_CONNECTIONS)
                mp_drawing.draw_landmarks(image, results.right_hand_landmarks, mp_holistic.HAND_CONNECTIONS)

                # وضعیت ضبط
                cv2.putText(image, f'REC ● [{frame_num + 1}/{SEQUENCE_LENGTH}]', (20, 80),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2, cv2.LINE_AA)
                cv2.putText(image, f'Action: {action} (#{sequence + 1})', (20, 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2, cv2.LINE_AA)
                cv2.imshow('SignAI Collector', image)

                # ذخیره داده‌های نرمال‌شده
                keypoints = extract_keypoints(results)
                npy_path = os.path.join(DATA_PATH, action, str(sequence), str(frame_num))
                np.save(npy_path, keypoints)

                if cv2.waitKey(1) & 0xFF == ord('q'):
                    cap.release()
                    cv2.destroyAllWindows()
                    exit()

cap.release()
cv2.destroyAllWindows()
print("\n🎉 ضبط داده‌ها با سیستم مختصات نرمال‌شده و ضد خطا تکمیل شد.")
