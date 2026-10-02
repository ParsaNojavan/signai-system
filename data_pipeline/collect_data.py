import os
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

def extract_keypoints(results):
    # بالاتنه (Pose landmarks 0 تا 22 -> 23 نقطه * 4 = 92)
    if results.pose_landmarks:
        pose = np.array([[res.x, res.y, res.z, res.visibility] for res in results.pose_landmarks.landmark[:23]]).flatten()
    else:
        pose = np.zeros(23 * 4)

    # دست چپ (21 نقطه * 3 = 63)
    if results.left_hand_landmarks:
        lh = np.array([[res.x, res.y, res.z] for res in results.left_hand_landmarks.landmark]).flatten()
    else:
        lh = np.zeros(21 * 3)

    # دست راست (21 نقطه * 3 = 63)
    if results.right_hand_landmarks:
        rh = np.array([[res.x, res.y, res.z] for res in results.right_hand_landmarks.landmark]).flatten()
    else:
        rh = np.zeros(21 * 3)

    # مجموع = 92 + 63 + 63 = 218
    return np.concatenate([pose, lh, rh])

# ==================== ساخت فولدرها ====================
for action in ACTIONS:
    for sequence in range(NO_SEQUENCES):
        os.makedirs(os.path.join(DATA_PATH, action, str(sequence)), exist_ok=True)

# ==================== حلقه ضبط دیتا ====================
cap = cv2.VideoCapture(0)

with mp_holistic.Holistic(min_detection_confidence=0.5, min_tracking_confidence=0.5) as holistic:
    for action in ACTIONS:
        for sequence in range(NO_SEQUENCES):
            for frame_num in range(SEQUENCE_LENGTH):
                ret, frame = cap.read()
                if not ret:
                    break

                # پردازش فریم با MediaPipe
                image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                image.flags.writeable = False
                results = holistic.process(image)
                image.flags.writeable = True
                image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

                # رسم لندمارک‌ها برای مانیتورینگ
                mp_drawing.draw_landmarks(image, results.pose_landmarks, mp_holistic.POSE_CONNECTIONS)
                mp_drawing.draw_landmarks(image, results.left_hand_landmarks, mp_holistic.HAND_CONNECTIONS)
                mp_drawing.draw_landmarks(image, results.right_hand_landmarks, mp_holistic.HAND_CONNECTIONS)

                # راهنمای شروع ضبط هر توالی
                if frame_num == 0:
                    cv2.putText(image, 'STARTING COLLECTION', (120, 200),
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 4, cv2.LINE_AA)
                    cv2.putText(image, f'Action: {action} | Video #{sequence}', (15, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2, cv2.LINE_AA)
                    cv2.imshow('OpenCV Feed', image)
                    cv2.waitKey(1500)  # مکث ۱.۵ ثانیه‌ای برای آماده شدن
                else:
                    cv2.putText(image, f'Action: {action} | Video #{sequence}', (15, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2, cv2.LINE_AA)
                    cv2.imshow('OpenCV Feed', image)

                # ذخیره نقاط در قالب npy
                keypoints = extract_keypoints(results)
                npy_path = os.path.join(DATA_PATH, action, str(sequence), str(frame_num))
                np.save(npy_path, keypoints)

                if cv2.waitKey(10) & 0xFF == ord('q'):
                    cap.release()
                    cv2.destroyAllWindows()
                    exit()

cap.release()
cv2.destroyAllWindows()
print("\n🎉 ضبط داده‌ها با موفقیت تکمیل شد.")
