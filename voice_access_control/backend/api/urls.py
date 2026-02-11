from django.urls import path
from .views import EnrollView, VerifyView

urlpatterns = [
    path('enroll/', EnrollView.as_view(), name='enroll'),
    path('verify/', VerifyView.as_view(), name='verify'),
]
