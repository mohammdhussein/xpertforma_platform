from datetime import date as dt_date, datetime
from django.utils.dateparse import parse_date
from rest_framework import status as drf_status
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from training.models import TrainingSession, TrainingPlanPlayer, PlayerSessionProgress
from accounts.permissions import IsPlayer


def _minutes_between(start_time, end_time):
    if not start_time or not end_time:
        return 0
    start_dt = datetime.combine(dt_date.today(), start_time)
    end_dt = datetime.combine(dt_date.today(), end_time)
    mins = int((end_dt - start_dt).total_seconds() // 60)
    return max(mins, 0)


class PlayerTrainingDayAPIView(APIView):
    permission_classes = [IsAuthenticated, IsPlayer]

    def get(self, request):
        user = request.user
        date_str = request.query_params.get("date")

        selected = parse_date(date_str) if date_str else dt_date.today()
        if not selected:
            return Response({"detail": "Invalid date format. Use YYYY-MM-DD."}, status=400)

        # plans assigned to this player
        plan_ids = TrainingPlanPlayer.objects.filter(player=user).values_list("plan_id", flat=True)

        # sessions for that day from assigned plans
        sessions = (
            TrainingSession.objects
            .filter(plan_id__in=plan_ids, session_date=selected)
            .select_related("plan")
            .order_by("start_time")
        )

        # existing progress rows for this player for these sessions
        progress_map = {
            p.session_id: p.status
            for p in PlayerSessionProgress.objects.filter(player=user, session__in=sessions)
        }

        items = []
        total_minutes = 0
        done_count = 0

        for s in sessions:
            dur = _minutes_between(s.start_time, s.end_time)
            total_minutes += dur

            st = progress_map.get(s.session_id, "not_started")
            if st == "done":
                done_count += 1

            items.append({
                "session_id": str(s.session_id),
                "title": s.title or "Training Session",
                "category": "Training Session",
                "duration_minutes": dur,
                "status": st,
                "start_time": str(s.start_time) if s.start_time else None,
                "end_time": str(s.end_time) if s.end_time else None,
                "plan": {"plan_id": str(s.plan.plan_id), "title": s.plan.title},
            })

        return Response({
            "date": str(selected),
            "month_label": selected.strftime("%B %Y"),
            "weekday_label": selected.strftime("%a"),
            "summary": {
                "total_items": len(items),
                "done": done_count,
                "total_minutes": total_minutes,
            },
            "items": items,
        })


class PlayerSessionStatusAPIView(APIView):
    permission_classes = [IsAuthenticated, IsPlayer]

    def post(self, request, session_id):
        user = request.user
        new_status = request.data.get("status")

        if new_status not in {"not_started", "in_progress", "done"}:
            return Response({"detail": "Invalid status."}, status=400)

        session = get_object_or_404(TrainingSession, session_id=session_id)

        # SECURITY: player must own this session via assigned plan
        is_assigned = TrainingPlanPlayer.objects.filter(plan=session.plan, player=user).exists()
        if not is_assigned:
            return Response({"detail": "Not allowed."}, status=403)

        obj, _ = PlayerSessionProgress.objects.get_or_create(player=user, session=session)
        obj.status = new_status
        obj.save(update_fields=["status", "updated_at"])

        return Response({"session_id": str(session.session_id), "status": obj.status}, status=drf_status.HTTP_200_OK)
