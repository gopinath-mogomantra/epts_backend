# ===========================================================
# performance/urls.py (Combined Version — 01-Nov-2025)
# ===========================================================
"""
Performance Management API Routes

This module provides comprehensive URL routing for the Performance
Evaluation system, including CRUD operations, dashboards, analytics,
reports, and export functionality.

Route Categories:
  📊 Evaluations - CRUD operations for performance evaluations
  📈 Dashboards - Performance dashboards and summaries
  📉 Analytics - Trends, comparisons, and insights
  🏆 Rankings - Leaderboards and rankings
  📄 Reports - Excel, PDF, and data exports
  🔍 Queries - Filtered data retrieval

Authentication:
  - All endpoints require authentication
  - Role-based access control applied
  - Object-level permissions enforced
"""
# ===========================================================

from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Main Views
from .views import (
    PerformanceEvaluationViewSet,
    EmployeePerformanceByIdView,
    PerformanceSummaryView,
    EmployeeDashboardView,
    PerformanceDashboardView,
    DepartmentPerformanceView,
    PerformanceTrendsView,
    PerformanceComparisonView,
    LeaderboardView,
)

# Report Views
from .views_reports import (
    PerformanceReportView,
    PerformanceExcelExportView,
    EmployeePerformancePDFView,
)

# -----------------------------------------------------------
# App Namespace
# -----------------------------------------------------------
app_name = "performance"

# -----------------------------------------------------------
# COMPREHENSIVE ROUTE DOCUMENTATION
# -----------------------------------------------------------
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    PERFORMANCE MANAGEMENT API ROUTES                          ║
╚══════════════════════════════════════════════════════════════════════════════╝

📊 EVALUATION ENDPOINTS (CRUD)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  GET     /api/performance/evaluations/                 → List all evaluations
  POST    /api/performance/evaluations/                 → Create evaluation (Admin/Manager)
  GET     /api/performance/evaluations/{id}/            → Retrieve evaluation
  PUT     /api/performance/evaluations/{id}/            → Update evaluation (Admin/Manager)
  PATCH   /api/performance/evaluations/{id}/            → Partial update
  DELETE  /api/performance/evaluations/{id}/            → Delete evaluation (Admin)
  
  🔹 Custom Actions:
  POST    /api/performance/evaluations/{id}/finalize/   → Lock evaluation
  POST    /api/performance/evaluations/{id}/unfinalize/ → Unlock evaluation (Admin)
  GET     /api/performance/evaluations/{id}/insights/   → Detailed analysis

  🔸 Query Parameters:
    - week_number=42              → Filter by ISO week
    - year=2025                   → Filter by year
    - evaluation_type=Manager     → Admin|Manager|Client|Self
    - department=ENG              → Filter by department
    - employee=EMP001             → Filter by employee
    - min_score=80&max_score=100  → Score range
    - rating=Outstanding          → Filter by rating
    - is_finalized=true           → Finalized only
    - search=keyword              → Search by employee/dept
    - ordering=-average_score     → Sort results
    - page=1&page_size=20         → Pagination

📈 DASHBOARD ENDPOINTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  GET     /api/performance/dashboard/                   → Employee self dashboard
  GET     /api/performance/dashboard/organization/      → Org-wide dashboard (Admin/Manager)
  GET     /api/performance/summary/                     → Weekly summary & leaderboard
  GET     /api/performance/department/{code}/           → Department analytics
  
  🔸 Query Parameters (dashboard):
    - include_insights=true       → Add detailed insights
    - weeks=12                    → Number of weeks for trends

  🔸 Query Parameters (organization):
    - include_rankings=true       → Add top 10 leaderboard

👤 EMPLOYEE PERFORMANCE ENDPOINTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  GET     /api/performance/employee/{emp_id}/           → Employee's all evaluations
  GET     /api/performance/evaluations/by-employee/{emp_id}/ → Alternate endpoint
  
  🔸 Query Parameters:
    - week=42                     → Filter by week
    - year=2025                   → Filter by year
    - evaluation_type=Manager     → Filter by type
    - include_insights=true       → Add analysis

📉 ANALYTICS & TRENDS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  GET     /api/performance/trends/                      → Performance trends
  GET     /api/performance/compare/                     → Compare entities
  GET     /api/performance/department/{code}/           → Department performance
  
  🔸 Query Parameters (trends):
    - department=ENG              → Filter by department
    - employee=EMP001             → Filter by employee
    - weeks=12                    → Number of weeks
    - evaluation_type=Manager     → Filter by type
  
  🔸 Query Parameters (compare):
    - type=employee|department    → Comparison type
    - ids=EMP001,EMP002,EMP003    → Comma-separated IDs
    - week=42&year=2025           → Filter by period

🏆 LEADERBOARD
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  GET     /api/performance/leaderboard/                 → Rankings
  
  🔸 Query Parameters:
    - week=42                     → Filter by week
    - year=2025                   → Filter by year
    - department=ENG              → Filter by department
    - evaluation_type=Manager     → Filter by type
    - limit=50                    → Number of results

📄 REPORTS & EXPORTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  GET     /api/performance/reports/                     → Generate reports
  GET     /api/performance/reports/excel/               → Export to Excel
  GET     /api/performance/reports/{emp_id}/pdf/        → Employee PDF report
  
  🔸 Query Parameters (reports):
    - format=json|csv|excel       → Output format
    - week=42                     → Filter by week
    - year=2025                   → Filter by year
    - department=ENG              → Filter by department
    - employee=EMP001             → Filter by employee
    - include_charts=true         → Add visualizations
  
  🔸 Query Parameters (excel):
    - week=42                     → Filter by week
    - year=2025                   → Filter by year
    - department=ENG              → Filter by department
    - include_summary=true        → Add summary sheet
  
  🔸 Query Parameters (pdf):
    - week=42                     → Filter by week
    - year=2025                   → Filter by year
    - include_trends=true         → Add trend charts

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔐 PERMISSION MATRIX
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Endpoint Type        │ Admin      │ Manager    │ Employee   │ Guest
─────────────────────┼────────────┼────────────┼────────────┼───────────
Evaluations (List)   │ ✅ All     │ ✅ Team    │ ✅ Self    │ ❌
Evaluations (Create) │ ✅ Yes     │ ✅ Yes     │ ❌         │ ❌
Evaluations (Update) │ ✅ Yes     │ ✅ Team    │ ❌         │ ❌
Evaluations (Delete) │ ✅ Yes     │ ❌         │ ❌         │ ❌
Finalize            │ ✅ Yes     │ ✅ Yes     │ ❌         │ ❌
Unfinalize          │ ✅ Yes     │ ❌         │ ❌         │ ❌
Dashboard (Self)     │ ✅ Yes     │ ✅ Yes     │ ✅ Yes     │ ❌
Dashboard (Org)      │ ✅ Yes     │ ✅ Yes     │ ❌         │ ❌
Analytics           │ ✅ Yes     │ ✅ Team    │ ✅ Self    │ ❌
Leaderboard         │ ✅ Yes     │ ✅ Yes     │ ✅ Yes     │ ❌
Reports (Basic)      │ ✅ Yes     │ ✅ Team    │ ✅ Self    │ ❌
Reports (Excel/PDF)  │ ✅ Yes     │ ✅ Yes     │ ❌         │ ❌

📊 RESPONSE FORMATS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
All JSON endpoints return consistent structure:

Success (200/201):
{
  "message": "Operation successful",
  "data": {...},
  "statistics": {...},     // For analytics endpoints
  "pagination": {...}      // For paginated endpoints
}

Error (400/403/404/500):
{
  "error": "Error message",
  "detail": "Additional context",
  "field_errors": {...}    // For validation errors
}

📝 EXAMPLE REQUESTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Create Performance Evaluation:
   POST /api/performance/evaluations/
   Body: {
     "employee": "EMP001",
     "evaluation_type": "Manager",
     "communication_skills": 85,
     "team_skills": 90,
     ...all 15 metrics...
   }

2. Get Employee Dashboard:
   GET /api/performance/dashboard/

3. View Department Performance:
   GET /api/performance/department/ENG/?week=42&year=2025

4. Compare Employees:
   GET /api/performance/compare/?type=employee&ids=EMP001,EMP002,EMP003

5. Export to Excel:
   GET /api/performance/reports/excel/?department=ENG&year=2025

6. Get Leaderboard:
   GET /api/performance/leaderboard/?week=42&limit=20

7. View Trends:
   GET /api/performance/trends/?department=ENG&weeks=12

8. Finalize Evaluation:
   POST /api/performance/evaluations/123/finalize/

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

For API documentation:
  - Swagger UI: /api/docs/
  - ReDoc: /api/redoc/
  - OpenAPI Schema: /api/schema/

Authentication:
  Authorization: Bearer <jwt_token>
  or
  Authorization: Token <token>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

# -----------------------------------------------------------
# DRF Router Configuration
# -----------------------------------------------------------
router = DefaultRouter()

# Register ViewSets
router.register(
    r"evaluations",
    PerformanceEvaluationViewSet,
    basename="performance"
)

# -----------------------------------------------------------
# URL Patterns
# -----------------------------------------------------------
urlpatterns = [
    # ═══════════════════════════════════════════════════════
    # Auto-generated CRUD Endpoints (from router)
    # ═══════════════════════════════════════════════════════
    # Includes:
    #   - /evaluations/
    #   - /evaluations/{id}/
    #   - /evaluations/{id}/finalize/
    #   - /evaluations/{id}/unfinalize/
    #   - /evaluations/{id}/insights/
    path("", include(router.urls)),

    # ═══════════════════════════════════════════════════════
    # Dashboard Endpoints
    # ═══════════════════════════════════════════════════════
    # Employee Self Dashboard
    path(
        "dashboard/",
        EmployeeDashboardView.as_view(),
        name="employee_dashboard"
    ),

    # Organization-wide Dashboard (Admin/Manager)
    path(
        "dashboard/organization/",
        PerformanceDashboardView.as_view(),
        name="organization_dashboard"
    ),

    # Weekly Performance Summary
    path(
        "summary/",
        PerformanceSummaryView.as_view(),
        name="performance_summary"
    ),

    # ═══════════════════════════════════════════════════════
    # Employee Performance Endpoints
    # ═══════════════════════════════════════════════════════
    # Get employee's all evaluations (primary endpoint)
    path(
        "employee/<str:emp_id>/",
        EmployeePerformanceByIdView.as_view(),
        name="employee_performance"
    ),

    # Alternate endpoint for employee evaluations
    path(
        "evaluations/by-employee/<str:emp_id>/",
        EmployeePerformanceByIdView.as_view(),
        name="evaluations_by_employee"
    ),

    # ═══════════════════════════════════════════════════════
    # Analytics & Trends
    # ═══════════════════════════════════════════════════════
    # Department Performance Analytics
    path(
        "department/<str:department_code>/",
        DepartmentPerformanceView.as_view(),
        name="department_performance"
    ),

    # Performance Trends Over Time
    path(
        "trends/",
        PerformanceTrendsView.as_view(),
        name="performance_trends"
    ),

    # Compare Employees or Departments
    path(
        "compare/",
        PerformanceComparisonView.as_view(),
        name="performance_comparison"
    ),

    # ═══════════════════════════════════════════════════════
    # Leaderboard & Rankings
    # ═══════════════════════════════════════════════════════
    path(
        "leaderboard/",
        LeaderboardView.as_view(),
        name="leaderboard"
    ),

    # ═══════════════════════════════════════════════════════
    # Reports & Export Endpoints
    # ═══════════════════════════════════════════════════════
    # General Performance Report
    path(
        "reports/",
        PerformanceReportView.as_view(),
        name="performance_report"
    ),

    # Export to Excel
    path(
        "reports/excel/",
        PerformanceExcelExportView.as_view(),
        name="export_excel"
    ),

    # Export Employee Performance to PDF
    path(
        "reports/<str:emp_id>/pdf/",
        EmployeePerformancePDFView.as_view(),
        name="export_pdf"
    ),
]

# -----------------------------------------------------------
# URL Pattern Summary (for debugging)
# -----------------------------------------------------------
"""
Complete URL Structure:

/api/performance/
├── evaluations/
│   ├── GET, POST                              # List/Create
│   ├── {id}/
│   │   ├── GET, PUT, PATCH, DELETE            # CRUD
│   │   ├── finalize/                          # POST - Lock evaluation
│   │   ├── unfinalize/                        # POST - Unlock (Admin)
│   │   └── insights/                          # GET - Detailed analysis
│   └── by-employee/{emp_id}/                  # GET - Employee's evaluations
│
├── dashboard/                                  # GET - Self dashboard
├── dashboard/organization/                     # GET - Org dashboard (Admin/Manager)
├── summary/                                    # GET - Weekly summary
│
├── employee/{emp_id}/                          # GET - Employee performance
├── department/{dept_code}/                     # GET - Department analytics
│
├── trends/                                     # GET - Performance trends
├── compare/                                    # GET - Compare entities
├── leaderboard/                                # GET - Rankings
│
└── reports/
    ├── /                                       # GET - General report
    ├── excel/                                  # GET - Excel export
    └── {emp_id}/pdf/                          # GET - PDF report

All endpoints support various query parameters for filtering, sorting, and pagination.
"""

# -----------------------------------------------------------
# Quick Reference
# -----------------------------------------------------------
"""
COMMON PATTERNS:

1. Get Latest Week Summary:
   GET /api/performance/summary/

2. Employee Views Own Performance:
   GET /api/performance/dashboard/

3. Manager Views Team Performance:
   GET /api/performance/evaluations/?department=ENG&week=42

4. Admin Exports Department Report:
   GET /api/performance/reports/excel/?department=ENG&year=2025

5. Compare Top Performers:
   GET /api/performance/compare/?type=employee&ids=EMP001,EMP002

6. View Department Trends:
   GET /api/performance/department/ENG/?include_trends=true

7. Get Organization Leaderboard:
   GET /api/performance/leaderboard/?limit=20

8. Create Manager Evaluation:
   POST /api/performance/evaluations/
   {
     "employee": "EMP001",
     "evaluation_type": "Manager",
     "week_number": 42,
     "year": 2025,
     ...metrics...
   }
"""