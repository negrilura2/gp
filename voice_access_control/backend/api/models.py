from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    full_name = models.CharField(max_length=64, blank=True, default='')
    phone = models.CharField(max_length=32, blank=True, default='')
    department = models.CharField(max_length=64, blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"UserProfile({self.user.username})"


class AdminSecret(models.Model):
    password_hash = models.CharField(max_length=128)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='admin_secrets')

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return "AdminSecret"


class AdminAccessLog(models.Model):
    action = models.CharField(max_length=64)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='admin_access_logs')
    success = models.BooleanField(default=False)
    client_ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"AdminAccessLog({self.action}, {self.success})"


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
    """
    验证与交互日志 (Enhanced for Hybrid Intelligence)
    User = 谁在说话 (预测结果)
    Intent = 意图 (OpenDoor, QueryInfo, etc.)
    Source = 来源 (LocalNLU vs CloudAgent)
    """
    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='verify_logs')
    wav_path = models.CharField(max_length=512, null=True, blank=True)
    predicted_user = models.CharField(max_length=128)
    score = models.FloatField()
    result = models.CharField(max_length=16)  # ACCEPT / REJECT
    
    # 新增字段用于 AI 分析
    intent = models.CharField(max_length=64, default='verify_only') # open_door, turn_on_light, query_knowledge, verify_only
    source = models.CharField(max_length=32, default='legacy')      # local_nlu, cloud_agent, legacy_http
    response_text = models.TextField(blank=True, default='')        # Agent 回复的内容
    latency_ms = models.IntegerField(default=0)                     # 处理耗时
    
    door_state = models.CharField(max_length=16, default='CLOSED')
    threshold = models.FloatField(default=0.75)
    client_ip = models.GenericIPAddressField(null=True, blank=True)
    error_msg = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"VerifyLog({self.predicted_user}, {self.intent}, {self.result})"
