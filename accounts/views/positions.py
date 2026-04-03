from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Position
from accounts.serializers.position import PositionSerializer


class PositionListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = PositionSerializer(Position.objects.order_by("id"), many=True)
        return Response({"positions": serializer.data})
