import os
import tempfile
from typing import List, Optional
import logging
import asyncio

from fastapi import FastAPI, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from voice_engine.agent_service import AgentService
from .service import VoiceService
from .stt_service import STTService
from .stream_processor import AudioBuffer

logger = logging.getLogger("voice_engine.api")

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
        while True:
            chunk = await websocket.receive_bytes()
            segments = buffer.process(chunk)

            for seg_bytes in segments:
                fd, tmp_path = tempfile.mkstemp(suffix=".wav")
                os.close(fd)
                with open(tmp_path, "wb") as f:
                    f.write(seg_bytes)

                try:
                    verify_res = await loop.run_in_executor(None, svc.verify, tmp_path)
                    trans_res = await loop.run_in_executor(None, stt.transcribe, tmp_path)
                    text = trans_res.get("text", "")

                    agent_response = {}
                    if text and len(text.strip()) > 1:
                        user_context = {
                            "user": verify_res.get("best_speaker"),
                            "score": verify_res.get("best_score")
                        }
                        agent_response = await agent_svc.process_command(text, user_context)

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

    uvicorn.run(
        "voice_engine.ai_app:app",
        host="0.0.0.0",
        port=9000,
        reload=False,
        loop="asyncio",
    )
