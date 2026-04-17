from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.queries.user_info import build_user_info_payload
from accounts.serializers.user_info import UserInfoSerializer


class UserInfoAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserInfoSerializer(build_user_info_payload(request.user))
        return Response(serializer.data)
