import numpy as np
from typing import Dict, Any, Optional, List, Tuple
from collections import deque


class SpellingPredictor:

    def __init__(self):
        self.history: List[Dict[str, Any]] = []
        self.max_history = 10

        self.trajectory_buffer_size = 18
        self.index_traj: deque = deque(maxlen=self.trajectory_buffer_size)
        self.pinky_traj: deque = deque(maxlen=self.trajectory_buffer_size)

        self.motion_cooldown = 0
        self.last_motion_letter: Optional[str] = None

    # =========================================================
    # Public API
    # =========================================================

    def predict(self, keypoints: np.ndarray) -> Dict[str, Any]:
        hand_pts, hand_mode = self._select_active_hand(keypoints)

        if hand_pts is None:
            self._reset_trajectories()
            return self._idle_response()

        wrist = hand_pts[0]
        hand_scale = max(self._distance(wrist, hand_pts[9]), 1e-4)
        
        rel_index_tip = (hand_pts[8] - wrist) / hand_scale
        rel_pinky_tip = (hand_pts[20] - wrist) / hand_scale

        self.index_traj.append(rel_index_tip[:2])
        self.pinky_traj.append(rel_pinky_tip[:2])

        features = self._extract_features(hand_pts, hand_mode)

        motion_candidate = self._detect_motion_letters(features, hand_mode)

        if motion_candidate is not None:
            best = motion_candidate
            candidates = [best]
        else:
            candidates = self._match_letter_candidates(features, hand_pts, hand_mode)
            best = candidates[0] if candidates else {"label": "uncertain", "score": 0.0}

        result = {
            "action": best["label"],
            "confidence": float(best["score"]),
            "hand_mode": hand_mode,
            "ready": True,
            "mode": "spelling",
            "fingers": {
                "thumb": features["thumb_extended"],
                "index": features["index_extended"],
                "middle": features["middle_extended"],
                "ring": features["ring_extended"],
                "pinky": features["pinky_extended"],
            },
            "features": self._debug_features(features),
            "candidates": candidates[:5],
        }

        self._update_history(result)
        result = self._apply_temporal_smoothing(result)

        return result

    def _reset_trajectories(self):
        self.index_traj.clear()
        self.pinky_traj.clear()

    # =========================================================
    # Hand selection
    # =========================================================

    def _select_active_hand(self, keypoints: np.ndarray) -> Tuple[Optional[np.ndarray], str]:
        if len(keypoints) < 218:
            return None, "none"

        left_hand = keypoints[92:155].reshape(21, 3)
        right_hand = keypoints[155:218].reshape(21, 3)

        left_score = float(np.sum(np.abs(left_hand)))
        right_score = float(np.sum(np.abs(right_hand)))

        if right_score > 0.05 and right_score >= left_score:
            return right_hand, "right"
        if left_score > 0.05:
            return left_hand, "left"

        return None, "none"

    def _idle_response(self) -> Dict[str, Any]:
        return {
            "action": "idle",
            "confidence": 0.0,
            "hand_mode": "none",
            "ready": True,
            "mode": "spelling",
            "fingers": {
                "thumb": False,
                "index": False,
                "middle": False,
                "ring": False,
                "pinky": False,
            },
            "features": {},
            "candidates": [],
        }

    # =========================================================
    # Geometry & Vector Helpers
    # =========================================================

    def _distance(self, a: np.ndarray, b: np.ndarray) -> float:
        return float(np.linalg.norm(a - b))

    def _safe_norm(self, v: np.ndarray) -> float:
        return float(np.linalg.norm(v) + 1e-6)

    def _angle(self, a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
        ba = a - b
        bc = c - b
        denom = self._safe_norm(ba) * self._safe_norm(bc)
        cosang = np.clip(float(np.dot(ba, bc) / denom), -1.0, 1.0)
        return float(np.degrees(np.arccos(cosang)))

    def _normalize(self, val: float, scale: float) -> float:
        return float(val / (scale + 1e-6))

    # =========================================================
    # Finger state detection
    # =========================================================

    def _is_finger_extended(self, pts: np.ndarray, tip: int, pip: int, mcp: int) -> bool:
        wrist = pts[0]
        d_tip = self._distance(pts[tip], wrist)
        d_pip = self._distance(pts[pip], wrist)
        angle = self._angle(pts[tip], pts[pip], pts[mcp])
        return (d_tip > d_pip * 1.08) and (angle > 138.0)

    def _is_finger_curled(self, pts: np.ndarray, tip: int, pip: int, mcp: int) -> bool:
        wrist = pts[0]
        d_tip = self._distance(pts[tip], wrist)
        d_pip = self._distance(pts[pip], wrist)
        angle = self._angle(pts[tip], pts[pip], pts[mcp])
        return (d_tip < d_pip * 1.05) or (angle < 125.0)

    def _is_thumb_open(self, pts: np.ndarray, scale: float) -> bool:
        tip = pts[4]
        ip = pts[3]
        mcp = pts[2]
        index_mcp = pts[5]

        reach = self._distance(tip, index_mcp) / scale
        angle = self._angle(tip, ip, mcp)
        return (reach > 0.42) and (angle > 130.0)

    # =========================================================
    # Feature Extraction
    # =========================================================

    def _extract_features(self, pts: np.ndarray, hand_mode: str) -> Dict[str, Any]:
        wrist = pts[0]
        index_mcp = pts[5]
        middle_mcp = pts[9]
        pinky_mcp = pts[17]

        hand_scale = max(self._distance(wrist, middle_mcp), self._distance(index_mcp, pinky_mcp), 1e-4)

        palm_dir = (middle_mcp - wrist) / self._safe_norm(middle_mcp - wrist)
        index_dir = (pts[8] - pts[5]) / self._safe_norm(pts[8] - pts[5])

        hand_points_up = bool(palm_dir[1] < -0.3)
        hand_points_down = bool(palm_dir[1] > 0.35)
        hand_points_horizontal = bool(abs(palm_dir[1]) <= 0.45 and abs(palm_dir[0]) > 0.5)

        thumb_ext = self._is_thumb_open(pts, hand_scale)
        index_ext = self._is_finger_extended(pts, 8, 6, 5)
        middle_ext = self._is_finger_extended(pts, 12, 10, 9)
        ring_ext = self._is_finger_extended(pts, 16, 14, 13)
        pinky_ext = self._is_finger_extended(pts, 20, 18, 17)

        d_thumb_index = self._normalize(self._distance(pts[4], pts[8]), hand_scale)
        d_thumb_middle = self._normalize(self._distance(pts[4], pts[12]), hand_scale)
        d_thumb_ring = self._normalize(self._distance(pts[4], pts[16]), hand_scale)
        d_thumb_pinky = self._normalize(self._distance(pts[4], pts[20]), hand_scale)
        d_index_middle = self._normalize(self._distance(pts[8], pts[12]), hand_scale)
        d_middle_ring = self._normalize(self._distance(pts[12], pts[16]), hand_scale)

        d_thumb_index_pip = self._normalize(self._distance(pts[4], pts[6]), hand_scale)
        d_thumb_middle_pip = self._normalize(self._distance(pts[4], pts[10]), hand_scale)
        d_thumb_ring_pip = self._normalize(self._distance(pts[4], pts[14]), hand_scale)

        v_index = pts[8] - pts[5]
        thumb_index_angle = self._angle(pts[4], pts[2], pts[2] + v_index)

        features = {
            "hand_scale": hand_scale,
            "hand_mode": hand_mode,
            "palm_dir": palm_dir,
            "index_dir": index_dir,
            "hand_points_up": hand_points_up,
            "hand_points_down": hand_points_down,
            "hand_points_horizontal": hand_points_horizontal,

            "thumb_extended": thumb_ext,
            "index_extended": index_ext,
            "middle_extended": middle_ext,
            "ring_extended": ring_ext,
            "pinky_extended": pinky_ext,

            "d_thumb_index": d_thumb_index,
            "d_thumb_middle": d_thumb_middle,
            "d_thumb_ring": d_thumb_ring,
            "d_thumb_pinky": d_thumb_pinky,
            "d_index_middle": d_index_middle,
            "d_middle_ring": d_middle_ring,

            "d_thumb_index_pip": d_thumb_index_pip,
            "d_thumb_middle_pip": d_thumb_middle_pip,
            "d_thumb_ring_pip": d_thumb_ring_pip,

            "thumb_index_angle": thumb_index_angle,
            "index_angle": self._angle(pts[8], pts[6], pts[5]),
            "middle_angle": self._angle(pts[12], pts[10], pts[9]),
            "ring_angle": self._angle(pts[16], pts[14], pts[13]),
            "pinky_angle": self._angle(pts[20], pts[18], pts[17]),
        }

        features["open_fingers"] = sum([index_ext, middle_ext, ring_ext, pinky_ext])
        return features

    # =========================================================
    # Motion Detection
    # =========================================================

    def _detect_motion_letters(self, f: Dict[str, Any], hand_mode: str) -> Optional[Dict[str, Any]]:

        if self.motion_cooldown > 0:
            self.motion_cooldown -= 1
            if self.last_motion_letter:
                return {"label": self.last_motion_letter, "score": 0.96}


        if f["pinky_extended"] and not f["index_extended"] and not f["middle_extended"]:
            if len(self.pinky_traj) >= 10:
                pts = np.array(self.pinky_traj)

                total_displacement = np.linalg.norm(pts[-1] - pts[0])
                path_length = np.sum(np.linalg.norm(np.diff(pts, axis=0), axis=1))

                y_motion = pts[:, 1]
                x_motion = pts[:, 0]
                dy = y_motion.max() - y_motion.min()
                dx = x_motion.max() - x_motion.min()

                
                if dy > 0.22 and dx > 0.15 and (path_length > total_displacement * 1.25):

                    self.pinky_traj.clear()
                    self.motion_cooldown = 4
                    self.last_motion_letter = "J"
                    return {"label": "J", "score": 0.94}


        if f["index_extended"] and not f["middle_extended"] and not f["ring_extended"] and not f["pinky_extended"]:
            if len(self.index_traj) >= 12:
                pts = np.array(self.index_traj)
                dxs = np.diff(pts[:, 0])

                sign_changes = 0
                for k in range(1, len(dxs)):
                    if (dxs[k] * dxs[k - 1] < -0.002):
                        sign_changes += 1

                total_span_x = pts[:, 0].max() - pts[:, 0].min()
                total_span_y = pts[:, 1].max() - pts[:, 1].min()

                if sign_changes >= 2 and total_span_x > 0.25 and total_span_y > 0.20:
                    self.index_traj.clear()
                    self.motion_cooldown = 4
                    self.last_motion_letter = "Z"
                    return {"label": "Z", "score": 0.95}

        return None

    # =========================================================
    # Rule matching
    # =========================================================

    def _match_letter_candidates(self, f: Dict[str, Any], pts: np.ndarray, hand_mode: str) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []

        def add(label: str, score: float):
            candidates.append({"label": label, "score": float(np.clip(score, 0.0, 1.0))})

        t = f["thumb_extended"]
        i = f["index_extended"]
        m = f["middle_extended"]
        r = f["ring_extended"]
        p = f["pinky_extended"]
        open_count = f["open_fingers"]

        if open_count == 4:
            if not t:
                score = 0.92
                if f["d_index_middle"] < 0.22:
                    score += 0.05
                add("B", score)
            else:
                add("5 / Open Palm", 0.90)

        elif open_count == 3:
            if i and m and r and not p:
                add("W", 0.94)
            elif m and r and p and not i:
                score = 0.88
                if f["d_thumb_index"] < 0.25:
                    score += 0.08
                add("F", score)

        elif i and m and not r and not p:
            if f["hand_points_horizontal"] and not t:
                add("H", 0.88)
            elif f["hand_points_down"] and t:
                add("P", 0.86)
            else:
                if t and (0.15 < f["d_thumb_index"] < 0.55):
                    add("K", 0.89)
                elif f["d_index_middle"] < 0.12 and abs(pts[8][0] - pts[12][0]) < 0.04:
                    add("R", 0.88)
                elif f["d_index_middle"] < 0.20:
                    add("U", 0.91)
                else:
                    add("V", 0.92)

        elif i and not m and not r and not p:
            if f["hand_points_down"] and t:
                add("Q", 0.85)
            elif f["hand_points_horizontal"] or (abs(f["index_dir"][1]) < 0.45 and t and f["d_thumb_index"] < 0.40):
                add("G", 0.89)
            elif t and (f["thumb_index_angle"] > 55.0 or f["d_thumb_index"] > 0.45):
                add("L", 0.95)
            elif not t or f["d_thumb_middle"] < 0.28:
                add("D", 0.92)

        elif not m and not r and not p and (100.0 < f["index_angle"] < 145.0):
            add("X", 0.86)

        elif p and not i and not m and not r:
            if t and f["d_thumb_pinky"] > 0.55:
                add("Y", 0.95)
            elif not t:
                add("I", 0.93)

        elif open_count == 0:
            is_curved = (f["index_angle"] < 155.0 and f["middle_angle"] < 155.0)

            if is_curved and f["d_thumb_index"] < 0.18:
                add("O", 0.88)
            elif is_curved and (0.22 <= f["d_thumb_index"] <= 0.65) and t:
                add("C", 0.87)
            else:
                if t and pts[4][1] < pts[6][1]:
                    add("A", 0.91)
                elif f["d_thumb_middle_pip"] < 0.22 and pts[4][1] < pts[10][1]:
                    add("S", 0.88)
                elif f["d_thumb_index_pip"] < 0.20:
                    add("T", 0.82)
                elif f["d_thumb_middle_pip"] < 0.25:
                    add("N", 0.79)
                elif f["d_thumb_ring_pip"] < 0.28:
                    add("M", 0.78)
                else:
                    add("E", 0.84)

        if not candidates:
            add("uncertain", 0.30)

        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates

    def _debug_features(self, f: Dict[str, Any]) -> Dict[str, Any]:
        out = {}
        for k, v in f.items():
            if isinstance(v, np.ndarray):
                out[k] = [round(float(x), 3) for x in v.tolist()]
            elif isinstance(v, (float, np.floating)):
                out[k] = round(float(v), 3)
            else:
                out[k] = v
        return out

    # =========================================================
    # Temporal smoothing
    # =========================================================

    def _update_history(self, result: Dict[str, Any]) -> None:
        self.history.append({
            "action": result["action"],
            "confidence": result["confidence"],
        })
        if len(self.history) > self.max_history:
            self.history.pop(0)

    def _apply_temporal_smoothing(self, result: Dict[str, Any]) -> Dict[str, Any]:

        if result["action"] in ["J", "Z"]:
            return result

        if len(self.history) < 4:
            return result

        recent_labels = [item["action"] for item in self.history[-4:]]
        for label in set(recent_labels):
            if recent_labels.count(label) >= 3 and label != "uncertain":
                result["action"] = label
                result["confidence"] = min(0.99, result["confidence"] + 0.05)
                break

        return result
