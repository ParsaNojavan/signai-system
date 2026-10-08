import numpy as np


POSE_LANDMARKS = 23
HAND_LANDMARKS = 21

POSE_FEATURES = POSE_LANDMARKS * 4
HAND_FEATURES = HAND_LANDMARKS * 3
TOTAL_FEATURES = POSE_FEATURES + HAND_FEATURES + HAND_FEATURES  # 218


def extract_keypoints(results) -> np.ndarray:
    # Pose
    if results.pose_landmarks:
        pose_raw = results.pose_landmarks.landmark

        left_shoulder = np.array(
            [pose_raw[11].x, pose_raw[11].y, pose_raw[11].z],
            dtype=np.float32
        )
        right_shoulder = np.array(
            [pose_raw[12].x, pose_raw[12].y, pose_raw[12].z],
            dtype=np.float32
        )

        mid_shoulder = (left_shoulder + right_shoulder) / 2.0
        shoulder_dist = np.linalg.norm(left_shoulder - right_shoulder)
        scale = shoulder_dist if shoulder_dist > 1e-4 else 1.0

        dx = right_shoulder[0] - left_shoulder[0]
        dy = right_shoulder[1] - left_shoulder[1]
        angle = -np.arctan2(dy, dx)

        rotation = np.array(
            [
                [np.cos(angle), -np.sin(angle)],
                [np.sin(angle),  np.cos(angle)],
            ],
            dtype=np.float32
        )

        pose_features = []
        for i in range(POSE_LANDMARKS):
            lm = pose_raw[i]
            coord = np.array([lm.x, lm.y, lm.z], dtype=np.float32)
            normalized = (coord - mid_shoulder) / scale
            rotated_xy = rotation @ normalized[:2]
            pose_features.extend([
                rotated_xy[0],
                rotated_xy[1],
                normalized[2],
                lm.visibility,
            ])

        pose_feat = np.asarray(pose_features, dtype=np.float32)
    else:
        pose_feat = np.zeros(POSE_FEATURES, dtype=np.float32)

    def extract_hand(hand_landmarks) -> np.ndarray:
        if hand_landmarks is None:
            return np.zeros(HAND_FEATURES, dtype=np.float32)

        raw = hand_landmarks.landmark
        wrist = np.array([raw[0].x, raw[0].y, raw[0].z], dtype=np.float32)

        hand_scale = np.linalg.norm(
            np.array([raw[9].x, raw[9].y, raw[9].z], dtype=np.float32) - wrist
        )
        if hand_scale <= 1e-4:
            hand_scale = 1.0

        points = [
            (np.array([lm.x, lm.y, lm.z], dtype=np.float32) - wrist) / hand_scale
            for lm in raw
        ]
        return np.asarray(points, dtype=np.float32).reshape(-1)

    left_hand_feat = extract_hand(results.left_hand_landmarks)
    right_hand_feat = extract_hand(results.right_hand_landmarks)

    features = np.concatenate([pose_feat, left_hand_feat, right_hand_feat]).astype(np.float32)

    if features.shape != (TOTAL_FEATURES,):
        raise ValueError(f"Feature shape mismatch: expected {(TOTAL_FEATURES,)}, got {features.shape}")

    return features


def mirror_keypoints(keypoints: np.ndarray) -> np.ndarray:
    mirrored = keypoints.astype(np.float32).copy()

    if mirrored.shape != (TOTAL_FEATURES,):
        raise ValueError(f"Keypoint shape mismatch: expected {(TOTAL_FEATURES,)}, got {mirrored.shape}")

    # Pose section
    pose = mirrored[:POSE_FEATURES].reshape(POSE_LANDMARKS, 4)
    pose[:, 0] *= -1  # mirror x

    # Swap left/right pose landmarks among first 23 landmarks
    pose_pairs = (
        (1, 4), (2, 5), (3, 6),
        (7, 8), (9, 10),
        (11, 12), (13, 14), (15, 16),
        (17, 18), (19, 20), (21, 22),
    )
    for a, b in pose_pairs:
        pose[[a, b]] = pose[[b, a]]

    # Hand sections
    left_start = POSE_FEATURES
    right_start = POSE_FEATURES + HAND_FEATURES

    left_hand = mirrored[left_start:right_start].reshape(HAND_LANDMARKS, 3).copy()
    right_hand = mirrored[right_start:right_start + HAND_FEATURES].reshape(HAND_LANDMARKS, 3).copy()

    left_hand[:, 0] *= -1
    right_hand[:, 0] *= -1

    mirrored[left_start:right_start] = right_hand.reshape(-1)
    mirrored[right_start:right_start + HAND_FEATURES] = left_hand.reshape(-1)

    return mirrored


def check_hand_activity(results) -> bool:
    left_visible = results.left_hand_landmarks is not None
    right_visible = results.right_hand_landmarks is not None

    if not (left_visible or right_visible):
        return False

    if not results.pose_landmarks:
        return False

    pose = results.pose_landmarks.landmark
    shoulder_y = (pose[11].y + pose[12].y) / 2.0

    if left_visible:
        left_wrist_y = results.left_hand_landmarks.landmark[0].y
        if left_wrist_y < shoulder_y + 0.35:
            return True

    if right_visible:
        right_wrist_y = results.right_hand_landmarks.landmark[0].y
        if right_wrist_y < shoulder_y + 0.35:
            return True

    return False
