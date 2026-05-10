from django.urls import path

from ai_assistant.views import AIChatView


urlpatterns = [
    path("chat/", AIChatView.as_view(), name="ai-chat"),
    path("chat", AIChatView.as_view(), name="ai-chat"),
]
