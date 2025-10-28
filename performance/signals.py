# ===========================================================
# performance/signals.py (Final — Auto Ranking on Save)
# ===========================================================
# Purpose:
# Automatically re-rank employees within each department
# whenever a new performance record is created or updated.
# ===========================================================

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from django.db.utils import OperationalError, ProgrammingError
import logging

from .models import PerformanceEvaluation

logger = logging.getLogger(__name__)


@receiver(post_save, sender=PerformanceEvaluation)
def auto_rank_on_save(sender, instance, created, **kwargs):
    """
    ✅ Automatically recalculates department-wise rankings whenever
    a PerformanceEvaluation is created or updated.

    Ranking Logic:
      • Scoped to same department, week, and year
      • Ordered by average_score (DESC)
      • Rank 1 = highest performer
    """

    dept = getattr(instance, "department", None)
    week = getattr(instance, "week_number", None)
    year = getattr(instance, "year", None)

    # 🚫 Skip incomplete or invalid records
    if not dept or not week or not year:
        logger.warning(
            f"[Auto-Rank] Skipped invalid evaluation (Dept={dept}, Week={week}, Year={year})."
        )
        return

    # ⚙️ Use transaction.on_commit to avoid race conditions
    def _update_ranks():
        try:
            evaluations = (
                PerformanceEvaluation.objects.filter(
                    department=dept,
                    week_number=week,
                    year=year,
                )
                .order_by("-average_score", "employee__user__first_name")
                .select_related("employee__user")
            )

            bulk_updates = []
            for idx, record in enumerate(evaluations, start=1):
                if record.rank != idx:
                    record.rank = idx
                    bulk_updates.append(record)

            if bulk_updates:
                PerformanceEvaluation.objects.bulk_update(bulk_updates, ["rank"])

            logger.info(
                f"🏁 [Auto-Rank] Department={dept.code} | Week={week} | Year={year} | Updated={len(bulk_updates)}"
            )

        except (OperationalError, ProgrammingError) as db_err:
            # Happens during migrations or early setup — safely ignored
            logger.warning(f"[Auto-Rank] Skipped during migration: {db_err}")
        except Exception as e:
            logger.exception(f"[Auto-Rank] Unexpected error: {e}")

    transaction.on_commit(_update_ranks)
