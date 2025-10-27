# ===========================================================
# performance/signals.py  (Final — Auto Ranking on Save)
# ===========================================================
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from .models import PerformanceEvaluation


@receiver(post_save, sender=PerformanceEvaluation)
def auto_rank_on_save(sender, instance, created, **kwargs):
    """
    ✅ Automatically recalculates department-wise rankings whenever
    a new PerformanceEvaluation is created or updated.

    Ranking logic:
      - Scoped to same department + week + year
      - Ordered by average_score (DESC)
      - Assigns rank 1 to highest performer
    """

    dept = instance.department
    week = instance.week_number
    year = instance.year

    # 🚫 Skip incomplete records
    if not dept or not week or not year:
        return

    # ⚙️ Use on_commit to avoid race condition during save()
    def _update_ranks():
        evaluations = (
            PerformanceEvaluation.objects.filter(
                department=dept,
                week_number=week,
                year=year,
            )
            .order_by("-average_score", "employee__user__first_name")
            .select_related("employee__user")
        )

        # Assign ranks efficiently (avoid multiple saves)
        bulk_updates = []
        for idx, record in enumerate(evaluations, start=1):
            if record.rank != idx:
                record.rank = idx
                bulk_updates.append(record)

        if bulk_updates:
            PerformanceEvaluation.objects.bulk_update(bulk_updates, ["rank"])

        print(
            f"🏁 [Auto-Rank] Dept={dept.code} | Week={week} | Year={year} | Updated={len(bulk_updates)}"
        )

    transaction.on_commit(_update_ranks)
