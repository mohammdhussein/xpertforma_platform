from django.shortcuts import get_object_or_404
from datetime import date as dt_date, datetime
from django.utils.dateparse import parse_date
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import IsPlayer
from training.models import TrainingSession, TrainingPlanPlayer, PlayerSessionProgress


def _duration_min(start_time, end_time):
    if not start_time or not end_time:
        return 0
    start_dt = datetime.combine(dt_date.today(), start_time)
    end_dt = datetime.combine(dt_date.today(), end_time)
    return max(int((end_dt - start_dt).total_seconds() // 60), 0)


class PlayerTrainingDayAPIView(APIView):
    permission_classes = [IsAuthenticated, IsPlayer]

    def get(self, request):
        user = request.user
        date_str = request.query_params.get("date")

        selected = parse_date(date_str) if date_str else dt_date.today()
        if not selected:
            return Response({"detail": "Invalid date format. Use YYYY-MM-DD."}, status=400)

        # player assigned plans
        assigned_plans = (
            TrainingPlanPlayer.objects
            .filter(player=user)
            .select_related("plan")
        )
        plan_ids = [a.plan_id for a in assigned_plans]

        # all sessions for that day across assigned plans
        sessions = (
            TrainingSession.objects
            .filter(plan_id__in=plan_ids, session_date=selected)
            .select_related("plan")
            .order_by("plan__title", "start_time")
        )

        session_ids = [s.session_id for s in sessions]

        # progress map for this player
        progress_map = {}
        if session_ids:
            progress_map = {
                p.session_id: p.status
                for p in PlayerSessionProgress.objects.filter(player=user, session_id__in=session_ids)
            }

        # group by plan
        plans_out = {}
        total_sessions = 0
        completed_sessions = 0
        total_duration = 0

        for s in sessions:
            pid = str(s.plan.plan_id)
            plans_out.setdefault(pid, {
                "plan_id": pid,
                "title": s.plan.title,
                "sessions": [],
            })

            st = progress_map.get(s.session_id, "not_started")
            dur = _duration_min(s.start_time, s.end_time)
            total_duration += dur

            total_sessions += 1
            if st == "completed":
                completed_sessions += 1

            plans_out[pid]["sessions"].append({
                "session_id": str(s.session_id),
                "title": s.title or "Session",
                "duration_min": dur,
                "status": st,
            })

        # compute per-plan completion
        final_plans = []
        for plan in plans_out.values():
            sessions_list = plan["sessions"]
            plan["sessions_count"] = len(sessions_list)
            plan["completed"] = (len(sessions_list) > 0 and all(x["status"] == "completed" for x in sessions_list))
            final_plans.append(plan)

        # stable order
        final_plans.sort(key=lambda x: x["title"].lower())

        return Response({
            "date": str(selected),
            "header": {
                "month": selected.strftime("%B %Y"),
                "day": selected.day,
                "weekday": selected.strftime("%a"),
            },
            "summary": {
                "completed_sessions": completed_sessions,
                "total_sessions": total_sessions,
                "total_duration_min": total_duration,
            },
            "plans": final_plans,
        })
class PlayerSessionStatusAPIView(APIView):
    permission_classes = [IsAuthenticated, IsPlayer]

    def post(self, request, session_id):
        user = request.user
        new_status = request.data.get("status")

        if new_status not in {"not_started", "in_progress", "completed"}:
            return Response({"detail": "Invalid status."}, status=400)

        session = get_object_or_404(TrainingSession, session_id=session_id)

        # ensure session belongs to a plan assigned to this player
        if not TrainingPlanPlayer.objects.filter(plan=session.plan, player=user).exists():
            return Response({"detail": "Not allowed."}, status=403)

        obj, _ = PlayerSessionProgress.objects.get_or_create(player=user, session=session)
        obj.status = new_status
        obj.save(update_fields=["status", "updated_at"])

        return Response({"session_id": str(session.session_id), "status": obj.status})