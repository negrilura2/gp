import logging
import edge_tts
import asyncio

logger = logging.getLogger("voice_engine.tts")

class TTSService:
    _instance = None

    def __init__(self, voice="zh-CN-XiaoxiaoNeural"):
        # You can change the voice to other Chinese voices like:
        # zh-CN-YunxiNeural (Male)
        # zh-CN-XiaoyiNeural (Female)
        self.voice = voice

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def generate_audio(self, text: str) -> bytes:
        """
        Generate audio from text using Edge TTS.
        Returns bytes of the audio (mp3 format).
        """
        if not text:
            return b""
            
        try:
            communicate = edge_tts.Communicate(text, self.voice)
            audio_data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]
            return audio_data
        except Exception as e:
            logger.error(f"TTS generation failed: {e}")
            return b""
