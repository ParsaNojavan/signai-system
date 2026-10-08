import json
import logging
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

from server.config import settings
from server.services.landmarks import TOTAL_FEATURES, mirror_keypoints

logger = logging.getLogger(__name__)


class SignPredictor:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.actions = self._load_actions()
        self.model = self._load_model()

    def _load_actions(self) -> list[str]:
        if not settings.actions_file.exists():
            logger.warning("Actions file not found at %s. Will attempt to load from checkpoint.", settings.actions_file)
            return []

        try:
            with open(settings.actions_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, dict) and "actions" in data:
                actions = data["actions"]
            elif isinstance(data, list):
                actions = data
            else:
                actions = []

            return [str(a) for a in actions]
        except Exception as e:
            logger.error("Failed to parse actions.json: %s", e)
            return []

    def _load_model(self):
        if not settings.model_path.exists():
            raise FileNotFoundError(f"Model file not found: {settings.model_path}")

        checkpoint = torch.load(
            settings.model_path,
            map_location=self.device,
            weights_only=False,
        )

        if str(settings.training_dir) not in sys.path:
            sys.path.insert(0, str(settings.training_dir))

        from model import SignLanguageBiLSTM

        checkpoint_classes = None
        for key in ("classes", "actions", "labels", "class_names"):
            if key in checkpoint and isinstance(checkpoint[key], list):
                checkpoint_classes = [str(c) for c in checkpoint[key]]
                break

        if checkpoint_classes:
            self.actions = checkpoint_classes
            logger.info("Loaded %d classes directly from model checkpoint.", len(self.actions))

        input_size = int(checkpoint.get("input_size", settings.input_size))
        hidden_size = int(checkpoint.get("hidden_size", 128))
        num_layers = int(checkpoint.get("num_layers", 2))
        dropout = float(checkpoint.get("dropout", 0.3))

        state_dict = checkpoint.get("model_state_dict")
        if state_dict is None:
            raise ValueError("Checkpoint does not contain 'model_state_dict'")

        fc_weight_key = next((k for k in reversed(state_dict.keys()) if "weight" in k and ("fc" in k or "classifier" in k or "out" in k)), None)
        if fc_weight_key is not None:
            model_num_classes = state_dict[fc_weight_key].shape[0]
        else:
            model_num_classes = int(checkpoint.get("num_classes", len(self.actions)))

        if len(self.actions) != model_num_classes:
            logger.warning(
                "⚠️ Class mismatch detected! Model outputs: %d, actions list length: %d.",
                model_num_classes,
                len(self.actions),
            )
            if len(self.actions) > model_num_classes:

                self.actions = self.actions[:model_num_classes]
                logger.warning("Truncated actions list to first %d items: %s", model_num_classes, self.actions)
            elif len(self.actions) < model_num_classes:

                missing_count = model_num_classes - len(self.actions)
                self.actions.extend([f"class_{i}" for i in range(len(self.actions), model_num_classes)])
                logger.warning("Padded missing classes with generic names: %s", self.actions)

        if input_size != TOTAL_FEATURES:
            raise ValueError(
                f"Model input_size mismatch. Model expects {input_size}, but pipeline extracts {TOTAL_FEATURES}"
            )

        # ۳. مقداردهی مدل
        model = SignLanguageBiLSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            num_classes=model_num_classes,
            dropout=dropout,
        ).to(self.device)

        model.load_state_dict(state_dict)
        model.eval()

        logger.info("✅ Model loaded successfully on [%s]", self.device)
        logger.info("✅ Active Classes (%d): %s", len(self.actions), self.actions)
        logger.info("✅ Input Feature Size: %d", input_size)

        return model

    @torch.inference_mode()
    def predict(self, sequence: np.ndarray) -> dict:
        expected_shape = (settings.sequence_length, settings.input_size)
        sequence = np.asarray(sequence, dtype=np.float32)

        if sequence.shape != expected_shape:
            raise ValueError(f"Expected sequence shape {expected_shape}, got {sequence.shape}")

        mirrored_sequence = np.stack([mirror_keypoints(frame) for frame in sequence])

        tensor_original = torch.from_numpy(sequence).unsqueeze(0).to(self.device)
        tensor_mirrored = torch.from_numpy(mirrored_sequence).unsqueeze(0).to(self.device)

        probs_original = F.softmax(self.model(tensor_original), dim=1)[0]
        probs_mirrored = F.softmax(self.model(tensor_mirrored), dim=1)[0]

        topk = min(2, len(self.actions))

        orig_vals, orig_idx = torch.topk(probs_original, topk)
        mirr_vals, mirr_idx = torch.topk(probs_mirrored, topk)

        if orig_vals[0] >= mirr_vals[0]:
            best_conf = float(orig_vals[0].item())
            best_idx = int(orig_idx[0].item())
            margin = float((orig_vals[0] - orig_vals[1]).item()) if topk > 1 else best_conf
            hand_mode = "original"
        else:
            best_conf = float(mirr_vals[0].item())
            best_idx = int(mirr_idx[0].item())
            margin = float((mirr_vals[0] - mirr_vals[1]).item()) if topk > 1 else best_conf
            hand_mode = "mirrored"

        if best_conf >= settings.confidence_threshold and margin >= settings.margin_threshold:
            action = self.actions[best_idx]
        else:
            action = "uncertain"

        return {
            "action": action,
            "confidence": round(best_conf, 3),
            "margin": round(margin, 3),
            "hand_mode": hand_mode,
            "ready": True,
        }
