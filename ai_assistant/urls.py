from django.urls import path

from ai_assistant.coach_ai_assistant_views import AIActionConfirmView, AIChatView


urlpatterns = [
    path("chat/", AIChatView.as_view(), name="ai-chat"),
    path("chat", AIChatView.as_view(), name="ai-chat"),
    path("actions/confirm/", AIActionConfirmView.as_view(), name="ai-actions-confirm"),
    path("actions/confirm", AIActionConfirmView.as_view(), name="ai-actions-confirm"),
]
