# ===========================================================
# reports/utils/pdf_generator.py
# ===========================================================
# Utility for generating PDF reports for employee performance
# using ReportLab. Reusable for both individual and bulk reports.
# ===========================================================

from io import BytesIO
from django.utils import timezone
from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

def generate_employee_performance_pdf(employee, evaluations, week=None):
    """
    Generates a printable PDF performance report for a given employee.

    Args:
        employee: Employee model instance
        evaluations: Queryset of PerformanceEvaluation objects
        week: Optional week (e.g., '2025-W43')

    Returns:
        HttpResponse (PDF file ready for download)
    """
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setTitle(f"Performance Report - {employee.user.emp_id}")

    # ---------------- HEADER ----------------
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(180, 800, "Employee Performance Report")

    pdf.setFont("Helvetica", 12)
    pdf.drawString(50, 770, f"Employee ID: {employee.user.emp_id}")
    pdf.drawString(50, 755, f"Name: {employee.user.first_name} {employee.user.last_name}")
    pdf.drawString(50, 740, f"Department: {employee.department.name if employee.department else 'N/A'}")
    if week:
        pdf.drawString(50, 725, f"Week: {week}")
    pdf.drawString(50, 710, f"Generated On: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # ---------------- TABLE HEADER ----------------
    y = 680
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(50, y, "Evaluation Type")
    pdf.drawString(200, y, "Average Score")
    pdf.drawString(350, y, "Remarks")
    pdf.line(45, y - 5, 550, y - 5)

    # ---------------- TABLE DATA ----------------
    pdf.setFont("Helvetica", 11)
    y -= 20
    for eval_obj in evaluations:
        avg_score = round(sum(eval_obj.metrics_breakdown.values()) / len(eval_obj.metrics_breakdown), 2)
        pdf.drawString(50, y, eval_obj.evaluation_type)
        pdf.drawString(200, y, str(avg_score))
        pdf.drawString(350, y, (eval_obj.remarks or "")[:60])
        y -= 20
        if y < 80:
            pdf.showPage()
            y = 800

    pdf.showPage()
    pdf.save()

    buffer.seek(0)
    filename = f"Performance_Report_{employee.user.emp_id}_{timezone.now().strftime('%Y%m%d')}.pdf"
    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
