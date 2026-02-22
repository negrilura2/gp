import os
import tempfile
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse

from .service import VoiceService


app = FastAPI(title="Voice AI Service", version="1.0.0")


@app.on_event("startup")
async def startup_event():
    VoiceService.get_instance()


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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("voice_engine.ai_app:app", host="0.0.0.0", port=9000, reload=False)

