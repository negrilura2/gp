from django.db import models
from django.contrib.auth.models import User


class VoiceTemplate(models.Model):
    """声纹模板记录"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='voice_templates')
    template_path = models.CharField(max_length=512)  # 存储路径 data/voiceprints/...
    embedding_count = models.IntegerField(default=1)   # 注册时使用的语音条数
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"VoiceTemplate({self.user.username}, count={self.embedding_count})"


class EnrollLog(models.Model):
    """注册日志"""
    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='enroll_logs')
    username = models.CharField(max_length=128)
    wav_count = models.IntegerField(default=0)         # 上传的音频文件数
    client_ip = models.GenericIPAddressField(null=True, blank=True)
    success = models.BooleanField(default=True)
    error_msg = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"EnrollLog({self.username}, {self.timestamp:%Y-%m-%d %H:%M})"


class VerifyLog(models.Model):
    """验证日志"""
    timestamp = models.DateTimeField(auto_now_add=True)
    wav_path = models.CharField(max_length=512, null=True, blank=True)
    predicted_user = models.CharField(max_length=128)
    score = models.FloatField()
    result = models.CharField(max_length=16)  # ACCEPT / REJECT
    threshold = models.FloatField(default=0.75)
    client_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"VerifyLog({self.predicted_user}, {self.score:.3f}, {self.result})"
