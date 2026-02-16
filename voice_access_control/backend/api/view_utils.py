import os
import sys
import json
import threading
import subprocess
import math
import logging
from datetime import datetime

import soundfile as sf

from django.conf import settings
from django.utils import timezone
from rest_framework import permissions

logger = logging.getLogger("api")

ROOT = os.fspath(settings.PROJECT_ROOT)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

MAX_UPLOAD_SIZE = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".wav"}


def get_client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    return xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR")


def validate_audio_file(f):
    ext = os.path.splitext(f.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"不支持的音频格式: {ext}，支持: {', '.join(ALLOWED_EXTENSIONS)}")
    if f.size > MAX_UPLOAD_SIZE:
        raise ValueError(f"文件过大: {f.size / 1024 / 1024:.1f}MB，限制: {MAX_UPLOAD_SIZE / 1024 / 1024:.0f}MB")
    if f.size == 0:
        raise ValueError("文件为空")
    try:
        f.seek(0)
        data, _ = sf.read(f)
        f.seek(0)
    except Exception:
        raise ValueError("音频解析失败，请上传 WAV 文件")
    if data is None or len(data) == 0:
        raise ValueError("音频文件为空")


def count_files(root, exts=None):
    if not os.path.exists(root):
        return 0
    total = 0
    for _, _, files in os.walk(root):
        for name in files:
            if exts is None or os.path.splitext(name)[1].lower() in exts:
                total += 1
    return total


def get_latest_file_path(root, exts=None):
    if not os.path.exists(root):
        return None
    latest_path = None
    latest_mtime = -1
    for base, _, files in os.walk(root):
        for name in files:
            if exts is None or os.path.splitext(name)[1].lower() in exts:
                path = os.path.join(base, name)
                try:
                    mtime = os.path.getmtime(path)
                except OSError:
                    continue
                if mtime > latest_mtime:
                    latest_mtime = mtime
                    latest_path = path
    return latest_path


def get_latest_file_info(root, exts=None):
    if not os.path.exists(root):
        return {"name": None, "mtime": None}
    latest_path = get_latest_file_path(root, exts)
    if latest_path is None:
        return {"name": None, "mtime": None}
    try:
        latest_mtime = os.path.getmtime(latest_path)
    except OSError:
        return {"name": None, "mtime": None}
    return {
        "name": os.path.basename(latest_path),
        "mtime": datetime.fromtimestamp(latest_mtime).isoformat(),
    }


def sanitize_json_value(value):
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: sanitize_json_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize_json_value(v) for v in value]
    return value


def load_json_if_exists(path):
    if not path or not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_staff


EVAL_STATUS_FILE = os.path.join(os.fspath(settings.REPORTS_DIR), "roc_status.json")
EVAL_STATUS_LOCK = threading.RLock()
EVAL_THREAD = None


def _read_eval_status():
    with EVAL_STATUS_LOCK:
        if not os.path.exists(EVAL_STATUS_FILE):
            return {"status": "idle"}
        try:
            with open(EVAL_STATUS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return {"status": "idle"}


def _write_eval_status(payload):
    with EVAL_STATUS_LOCK:
        os.makedirs(os.fspath(settings.REPORTS_DIR), exist_ok=True)
        with open(EVAL_STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)


def _set_eval_status(status_value, **kwargs):
    with EVAL_STATUS_LOCK:
        payload = {"status": status_value, "updated_at": timezone.now().isoformat()}
        payload.update(kwargs)
        _write_eval_status(payload)
        return payload


def get_eval_thread():
    return EVAL_THREAD


def _start_eval_thread(model_path):
    global EVAL_THREAD

    def _run():
        model_name = os.path.basename(model_path)
        _set_eval_status("running", model=model_name, started_at=timezone.now().isoformat())
        feature_dir = os.fspath(settings.FEATURES_DIR)
        cmd = [
            sys.executable,
            "-m",
            "scripts.eval.eval_threshold",
            "--model",
            model_path,
            "--feature_dir",
            feature_dir,
            "--out_dir",
            os.fspath(settings.REPORTS_DIR),
            "--max_pairs",
            "20000",
        ]
        try:
            result = subprocess.run(
                cmd,
                cwd=os.fspath(settings.PROJECT_ROOT),
                env={**os.environ, "MPLBACKEND": "Agg"},
                capture_output=True,
                text=True,
                check=True,
            )
            output = (result.stdout or "").strip()
            _set_eval_status("ok", model=model_name, output=output, finished_at=timezone.now().isoformat())
        except subprocess.CalledProcessError as e:
            msg = (e.stderr or e.stdout or "评估失败").strip()
            _set_eval_status("failed", model=model_name, error=msg, finished_at=timezone.now().isoformat())

    EVAL_THREAD = threading.Thread(target=_run, daemon=True)
    EVAL_THREAD.start()
