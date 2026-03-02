import os
import signal
import sys
import tempfile
import time
from typing import List, Optional
import logging
import asyncio

from fastapi import FastAPI, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
# --- DB Imports ---
import django
# Add backend directory to sys.path so django can find 'backend.settings'
current_dir = os.path.dirname(os.path.abspath(__file__)) # voice_access_control/voice_engine
project_root = os.path.dirname(current_dir) # voice_access_control
backend_dir = os.path.join(project_root, "backend") # voice_access_control/backend
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()
from django.contrib.auth.models import User
from api.models import VerifyLog
# ------------------

from voice_engine.services.agent_service import AgentService
from .service import VoiceService
from .services.stt_service import STTService
from voice_engine.services.stream_processor import AudioBuffer

logger = logging.getLogger("voice_engine.api")

# Handle Ctrl+C gracefully
def signal_handler(sig, frame):
    logger.info("Received shutdown signal, stopping services...")
    # Explicitly stop the event loop if running
    try:
        loop = asyncio.get_running_loop()
        loop.stop()
    except RuntimeError:
        pass
    # Exit without traceback
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

app = FastAPI(title="Voice AI Service", version="1.0.0")

@app.on_event("startup")
async def startup_event():
    # Preload models
    VoiceService.get_instance()
    # Initialize STT with a small model by default
    STTService.get_instance(model_size="tiny")
    # Initialize Agent Service
    try:
        AgentService.get_instance()
    except Exception as e:
        logger.warning(f"Failed to initialize AgentService: {e}")


@app.get("/health")
async def health():
    svc = VoiceService.get_instance()
    return {
        "status": "ok",
        "model_path": svc.model_path,
        "device": str(svc.device),
        "feature_type": svc.feature_type,
        "n_mels": int(svc.n_mels),
    }


def _save_upload_to_temp(upload: UploadFile) -> str:
    suffix = os.path.splitext(upload.filename or "")[1] or ".wav"
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    data = upload.file.read()
    with open(path, "wb") as f:
        f.write(data)
    return path


@app.post("/verify")
async def verify(file: UploadFile = File(...), threshold: Optional[float] = Form(None)):
    tmp_path = _save_upload_to_temp(file)
    svc = VoiceService.get_instance()
    try:
        result = svc.verify(tmp_path, threshold=threshold)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
    return JSONResponse(result)


@app.post("/enroll")
async def enroll(
    user_id: str = Form(...),
    files: List[UploadFile] = File(...),
):
    tmp_paths = []
    svc = VoiceService.get_instance()
    try:
        for up in files:
            tmp_paths.append(_save_upload_to_temp(up))
        result = svc.enroll(user_id, tmp_paths)
    finally:
        for p in tmp_paths:
            try:
                os.remove(p)
            except OSError:
                pass
    return JSONResponse(result)


@app.post("/reload")
async def reload(model_path: Optional[str] = Form(None), device: Optional[str] = Form(None)):
    svc = VoiceService.reload(model_path=model_path, device=device)
    return {
        "status": "ok",
        "model_path": svc.model_path,
        "device": str(svc.device),
    }


@app.get("/voiceprint/{user_id}")
async def get_voiceprint(user_id: str):
    svc = VoiceService.get_instance()
    emb = svc.get_feature(user_id)
    if emb is None:
        return JSONResponse({"error": "Voiceprint not found"}, status_code=404)
    return {"user_id": user_id, "embedding": emb.tolist()}


@app.delete("/voiceprint/{user_id}")
async def delete_voiceprint(user_id: str):
    svc = VoiceService.get_instance()
    deleted = svc.delete_feature(user_id)
    if not deleted:
        return JSONResponse({"error": "Voiceprint not found or failed to delete"}, status_code=404)
    return {"status": "deleted", "user_id": user_id}


@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...), beam_size: int = Form(5)):
    tmp_path = _save_upload_to_temp(file)
    stt = STTService.get_instance()
    try:
        result = stt.transcribe(tmp_path, beam_size=beam_size)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
    return JSONResponse(result)


@app.websocket("/ws/audio")
async def websocket_audio(websocket: WebSocket):
    """
    Real-time audio streaming endpoint.
    Accepts binary PCM 16-bit mono 16kHz chunks.
    """
    await websocket.accept()
    buffer = AudioBuffer()
    svc = VoiceService.get_instance()
    stt = STTService.get_instance()
    agent_svc = AgentService.get_instance()
    loop = asyncio.get_running_loop()

    try:
        chunk_count = 0
        while True:
            chunk = await websocket.receive_bytes()
            chunk_count += 1
            if chunk_count % 100 == 0:
                logger.debug(f"Received {chunk_count} chunks...")
                
            segments = buffer.process(chunk)

            if segments:
                logger.info(f"VAD triggered! Processing {len(segments)} segment(s)...")

            for seg_bytes in segments:
                fd, tmp_path = tempfile.mkstemp(suffix=".wav")
                os.close(fd)
                with open(tmp_path, "wb") as f:
                    f.write(seg_bytes)

                try:
                    start_time = time.time()
                    verify_res = await loop.run_in_executor(None, svc.verify, tmp_path)
                    trans_res = await loop.run_in_executor(None, stt.transcribe, tmp_path)
                    text = trans_res.get("text", "")

                    agent_response = {}
                    intent = "verify_only"
                    source = "legacy"
                    
                    if text and len(text.strip()) > 1:
                        user_context = {
                            "user": verify_res.get("best_speaker"),
                            "score": verify_res.get("best_score")
                        }
                        agent_response = await agent_svc.process_command(text, user_context)
                        # Extract intent and source from agent response
                        if agent_response.get("status") == "success":
                            source = agent_response.get("source", "cloud_agent")
                            # Simple heuristic for intent based on source or content
                            if source == "local_nlu":
                                intent = "command"
                            elif "Tool called" in agent_response.get("response", ""):
                                intent = "agent_action"
                            else:
                                intent = "chat"

                    latency = int((time.time() - start_time) * 1000)

                    # --- Async DB Logging ---
                    try:
                        # Find user object
                        username = verify_res.get("best_speaker")
                        user_obj = await loop.run_in_executor(None, lambda: User.objects.filter(username=username).first())
                        
                        await loop.run_in_executor(None, lambda: VerifyLog.objects.create(
                            user=user_obj,
                            predicted_user=username,
                            score=verify_res.get("best_score", 0.0),
                            result=verify_res.get("result", "REJECT"),
                            intent=intent,
                            source=source,
                            response_text=agent_response.get("response", "")[:500], # Truncate if too long
                            latency_ms=latency,
                            client_ip=websocket.client.host
                        ))
                    except Exception as db_err:
                        logger.error(f"Failed to write log to DB: {db_err}")
                    # ------------------------

                    response = {
                        "type": "result",
                        "identity": {
                            "user": verify_res.get("best_speaker"),
                            "score": verify_res.get("best_score"),
                            "status": verify_res.get("result")
                        },
                        "text": text,
                        "language": trans_res.get("language"),
                        "agent": agent_response
                    }
                    await websocket.send_json(response)

                except Exception as e:
                    logger.error(f"Stream processing error: {e}")
                    await websocket.send_json({"type": "error", "message": str(e)})
                finally:
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass

    except asyncio.CancelledError:
        logger.info("WebSocket task cancelled (server shutdown)")
        raise
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        try:
            await websocket.close()
        except:
            pass


if __name__ == "__main__":
    import uvicorn

    # Use default signal handlers to allow Ctrl+C to propagate to uvicorn
    # Restore default handlers before running uvicorn
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    signal.signal(signal.SIGTERM, signal.SIG_DFL)

    uvicorn.run(
        "voice_engine.ai_app:app",
        host="0.0.0.0",
        port=9000,
        reload=False,
        loop="asyncio",
    )
