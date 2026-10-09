import asyncio
import collections
import logging

import cv2
import mediapipe as mp
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from server.config import settings
from server.dependencies import get_current_user_from_ws
from server.services.landmarks import check_hand_activity, extract_keypoints


logger = logging.getLogger(__name__)
router = APIRouter(tags=["inference"])

mp_holistic = mp.solutions.holistic


@router.websocket("/ws/inference")
async def websocket_inference(websocket: WebSocket):
    user = await get_current_user_from_ws(websocket)
    if user is None:
        return

    await websocket.accept()
    logger.info("WebSocket connected: user=%s", user.username)

    predictor = websocket.app.state.predictor
    sequence_buffer = collections.deque(maxlen=settings.sequence_length)

    idle_response = {
        "action": "idle",
        "confidence": 0.0,
        "hand_mode": "none",
        "ready": False,
    }

    try:
        with mp_holistic.Holistic(
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
            model_complexity=settings.model_complexity,
        ) as holistic:
            while True:
                frame_bytes = await websocket.receive_bytes()

                if len(frame_bytes) > settings.max_frame_bytes:
                    await websocket.send_json({
                        "action": "invalid_frame",
                        "confidence": 0.0,
                        "hand_mode": "none",
                        "ready": False,
                        "detail": "Frame too large",
                    })
                    continue

                encoded = np.frombuffer(frame_bytes, dtype=np.uint8)
                frame = cv2.imdecode(encoded, cv2.IMREAD_COLOR)

                if frame is None:
                    await websocket.send_json({
                        "action": "invalid_frame",
                        "confidence": 0.0,
                        "hand_mode": "none",
                        "ready": False,
                        "detail": "Could not decode frame",
                    })
                    continue

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                rgb.flags.writeable = False
                results = await asyncio.to_thread(holistic.process, rgb)

                if not check_hand_activity(results):
                    sequence_buffer.clear()
                    await websocket.send_json(idle_response)
                    continue

                keypoints = extract_keypoints(results)
                sequence_buffer.append(keypoints)

                if len(sequence_buffer) < settings.sequence_length:
                    await websocket.send_json({
                        "action": "buffering",
                        "confidence": 0.0,
                        "hand_mode": "none",
                        "ready": False,
                        "frames_collected": len(sequence_buffer),
                        "frames_required": settings.sequence_length,
                    })
                    continue

                sequence = np.asarray(sequence_buffer, dtype=np.float32)
                response = await asyncio.to_thread(predictor.predict, sequence)
                await websocket.send_json(response)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: user=%s", user.username)

    except Exception:
        logger.exception("Inference websocket failed for user=%s", user.username)
        try:
            await websocket.close(code=1011, reason="Internal inference error")
        except Exception:
            pass
