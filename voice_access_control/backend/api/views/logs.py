from django.db import models
from rest_framework import generics, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response

from ..models import VerifyLog, EnrollLog
from ..serializers import VerifyLogSerializer, EnrollLogSerializer
from ..view_utils import IsAdminUser


class VerifyLogListView(generics.ListAPIView):
    serializer_class = VerifyLogSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        qs = VerifyLog.objects.all()
        result = self.request.query_params.get("result")
        if result:
            qs = qs.filter(result=result.upper())
        predicted = self.request.query_params.get("predicted")
        user_param = self.request.query_params.get("user")
        name = predicted or user_param
        if name:
            qs = qs.filter(predicted_user__icontains=name)

        actor = self.request.query_params.get("actor")
        if actor:
            qs = qs.filter(user__username__icontains=actor)

        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")
        if start_date:
            qs = qs.filter(timestamp__date__gte=start_date)
        if end_date:
            qs = qs.filter(timestamp__date__lte=end_date)

        def _to_float(param):
            try:
                return float(param)
            except (TypeError, ValueError):
                return None

        min_score = _to_float(self.request.query_params.get("min_score"))
        max_score = _to_float(self.request.query_params.get("max_score"))
        if min_score is not None:
            qs = qs.filter(score__gte=min_score)
        if max_score is not None:
            qs = qs.filter(score__lte=max_score)

        min_thr = _to_float(self.request.query_params.get("min_threshold"))
        max_thr = _to_float(self.request.query_params.get("max_threshold"))
        if min_thr is not None:
            qs = qs.filter(threshold__gte=min_thr)
        if max_thr is not None:
            qs = qs.filter(threshold__lte=max_thr)
        return qs


class MyVerifyLogListView(generics.ListAPIView):
    serializer_class = VerifyLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = VerifyLog.objects.filter(models.Q(user=user) | models.Q(predicted_user=user.username))
        return qs.order_by("-timestamp")[:100]


class VerifyLogBulkDeleteView(APIView):
    permission_classes = [IsAdminUser]

    def delete(self, request):
        ids = request.data.get("ids") or []
        if not isinstance(ids, list):
            return Response({"error": "ids 必须是列表"}, status=status.HTTP_400_BAD_REQUEST)
        ids = [int(i) for i in ids if str(i).isdigit()]
        if not ids:
            return Response({"deleted": 0})
        deleted, _ = VerifyLog.objects.filter(id__in=ids).delete()
        return Response({"deleted": deleted})


class EnrollLogListView(generics.ListAPIView):
    serializer_class = EnrollLogSerializer
    permission_classes = [IsAdminUser]
    queryset = EnrollLog.objects.all()
