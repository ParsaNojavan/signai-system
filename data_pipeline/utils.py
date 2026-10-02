import json
import os
import numpy as np

def load_actions(config_path="../dataset/actions.json") -> np.ndarray:

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"فایل کانفیگ کلمات در مسیر {config_path} پیدا نشد.")

    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    actions = data.get("actions", [])
    if not actions:
        raise ValueError("لیست actions در فایل کانفیگ خالی است!")

    if "idle" not in actions:
        print("⚠️ هشدار: کلاس 'idle' یافت نشد. به انتهای لیست اضافه شد.")
        actions.append("idle")

    return np.array(actions)
