# ===========================================================
# employee/urls.py (Enhanced Version — 01-Nov-2025)
# ===========================================================
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DepartmentViewSet,
    EmployeeViewSet,
    EmployeeCSVUploadView,
    AdminProfileView,
    ManagerProfileView,
    EmployeeProfileView,
    HealthCheckView,
)

# -----------------------------------------------------------
# App Namespace
# -----------------------------------------------------------
app_name = "employee"

# -----------------------------------------------------------
# COMPREHENSIVE ROUTE DOCUMENTATION
# -----------------------------------------------------------
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    EMPLOYEE MANAGEMENT API ROUTES                             ║
╚══════════════════════════════════════════════════════════════════════════════╝

📋 DEPARTMENT ENDPOINTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  GET     /api/employee/departments/                    → List all departments
  POST    /api/employee/departments/                    → Create department (Admin)
  GET     /api/employee/departments/{code}/             → Retrieve department
  PUT     /api/employee/departments/{code}/             → Update department (Admin)
  PATCH   /api/employee/departments/{code}/             → Partial update (Admin)
  DELETE  /api/employee/departments/{code}/             → Deactivate department (Admin)
  DELETE  /api/employee/departments/{code}/?force=true  → Permanent delete (Admin)
  
  🔹 Custom Actions:
  GET     /api/employee/departments/{code}/employees/   → List dept employees
  GET     /api/employee/departments/statistics/         → Department stats (Admin)

  🔸 Query Parameters:
    - include_inactive=true    → Show inactive departments (Admin only)
    - search=keyword           → Search by name, code, description
    - ordering=name,-created_at → Sort results
    - page=1&page_size=20      → Pagination

👥 EMPLOYEE ENDPOINTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  GET     /api/employee/employees/                      → List employees
  POST    /api/employee/employees/                      → Create employee (Admin/Manager)
  GET     /api/employee/employees/{emp_id}/             → Retrieve employee
  PUT     /api/employee/employees/{emp_id}/             → Update employee (Admin/Manager)
  PATCH   /api/employee/employees/{emp_id}/             → Partial update
  DELETE  /api/employee/employees/{emp_id}/             → Soft delete (Admin/Manager)
  
  🔹 Custom Actions:
  GET     /api/employee/employees/{emp_id}/team/        → View manager's team
  GET     /api/employee/employees/statistics/           → Employee stats (Admin)

  🔸 Query Parameters:
    - status=Active|Inactive              → Filter by status
    - department=HR|dept_code|dept_id     → Filter by department
    - role=Admin|Manager|Employee         → Filter by role
    - manager=EMP001                      → Filter by manager
    - joining_from=2024-01-01             → Filter by joining date (from)
    - joining_to=2024-12-31               → Filter by joining date (to)
    - search=name|email|emp_id            → Search employees
    - ordering=joining_date,-created_at   → Sort results
    - page=1&page_size=20                 → Pagination

📤 BULK OPERATIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  POST    /api/employee/upload_csv/                     → Bulk CSV upload (Admin)
  
  🔸 Form Data:
    - file (required)         → CSV file (max 5MB)
    - send_emails (optional)  → Send welcome emails (default: true)
  
  🔸 CSV Format:
    Required columns: Emp Id, First Name, Last Name, Email, Dept Code, Role, Joining Date
    Optional columns: Contact Number, Designation, Manager Emp Id

👤 PROFILE ENDPOINTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  GET     /api/employee/admin/profile/                  → Get admin profile
  PATCH   /api/employee/admin/profile/                  → Update admin profile
  PUT     /api/employee/admin/profile/                  → Full update admin profile

  GET     /api/employee/manager/profile/                → Get manager profile
  PATCH   /api/employee/manager/profile/                → Update manager profile
  PUT     /api/employee/manager/profile/                → Full update manager profile

  GET     /api/employee/profile/                        → Get employee profile
  PATCH   /api/employee/profile/                        → Update employee profile
  PUT     /api/employee/profile/                        → Full update employee profile

🏥 SYSTEM ENDPOINTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  GET     /api/employee/health/                         → Health check (public)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔐 PERMISSION MATRIX
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Endpoint Type        │ Admin      │ Manager    │ Employee   │ Guest
─────────────────────┼────────────┼────────────┼────────────┼───────────
Departments (List)   │ ✅ Full    │ ✅ Read    │ ✅ Read    │ ❌
Departments (CUD)    │ ✅ Full    │ ❌         │ ❌         │ ❌
Employees (List)     │ ✅ All     │ ✅ Team    │ ✅ Self    │ ❌
Employees (Create)   │ ✅ Full    │ ✅ Full    │ ❌         │ ❌
Employees (Update)   │ ✅ Full    │ ✅ Team    │ ✅ Self    │ ❌
Employees (Delete)   │ ✅ Full    │ ✅ Team    │ ❌         │ ❌
CSV Upload           │ ✅ Full    │ ❌         │ ❌         │ ❌
Profile (Own)        │ ✅ Full    │ ✅ Full    │ ✅ Full    │ ❌
Statistics           │ ✅ Full    │ ❌         │ ❌         │ ❌
Health Check         │ ✅         │ ✅         │ ✅         │ ✅

📝 RESPONSE FORMAT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
All endpoints return JSON responses with consistent structure:

Success (200/201):
{
  "message": "Operation successful",
  "data": {...},
  "count": 100,              // For list endpoints
  "total_pages": 10,         // For paginated endpoints
  "current_page": 1
}

Error (400/403/404/500):
{
  "error": "Error message",
  "detail": "Additional details",
  "field_errors": {          // For validation errors
    "email": ["This field is required"]
  }
}

📊 EXAMPLE REQUESTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. List all active employees in HR department:
   GET /api/employee/employees/?department=HR&status=Active

2. Search employees by name:
   GET /api/employee/employees/?search=John

3. Get employees who joined in 2024:
   GET /api/employee/employees/?joining_from=2024-01-01&joining_to=2024-12-31

4. Get manager's team:
   GET /api/employee/employees/EMP001/team/

5. Upload employees via CSV:
   POST /api/employee/upload_csv/
   Form-data: file=employees.csv, send_emails=true

6. Update employee profile:
   PATCH /api/employee/employees/EMP001/
   Body: {"contact_number": "+919876543210", "designation": "Senior Developer"}

7. Get department statistics:
   GET /api/employee/departments/statistics/

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

For detailed API documentation, visit:
  - Swagger UI: /api/docs/
  - ReDoc: /api/redoc/
  - OpenAPI Schema: /api/schema/

For authentication, include token in header:
  Authorization: Bearer <your_jwt_token>
  or
  Authorization: Token <your_token>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

# -----------------------------------------------------------
# DRF Router Configuration
# -----------------------------------------------------------
router = DefaultRouter()

# Register ViewSets with router
# These automatically generate CRUD endpoints
router.register(
    r"departments",
    DepartmentViewSet,
    basename="departments"
)

router.register(
    r"employees",
    EmployeeViewSet,
    basename="employees"
)

# -----------------------------------------------------------
# URL Patterns
# -----------------------------------------------------------
urlpatterns = [
    # ═══════════════════════════════════════════════════════
    # Auto-generated CRUD Endpoints (from router)
    # ═══════════════════════════════════════════════════════
    # Includes all ViewSet endpoints:
    #   - departments/
    #   - departments/{code}/
    #   - employees/
    #   - employees/{emp_id}/
    # Plus custom actions defined with @action decorator
    path("", include(router.urls)),

    # ═══════════════════════════════════════════════════════
    # Bulk Operations
    # ═══════════════════════════════════════════════════════
    path(
        "upload_csv/",
        EmployeeCSVUploadView.as_view(),
        name="employee_csv_upload"
    ),

    # ═══════════════════════════════════════════════════════
    # Role-Based Profile Management
    # ═══════════════════════════════════════════════════════
    # Admin Profile
    path(
        "admin/profile/",
        AdminProfileView.as_view(),
        name="admin_profile"
    ),

    # Manager Profile
    path(
        "manager/profile/",
        ManagerProfileView.as_view(),
        name="manager_profile"
    ),

    # Employee Profile (Regular employees)
    path(
        "profile/",
        EmployeeProfileView.as_view(),
        name="employee_profile"
    ),

    # ═══════════════════════════════════════════════════════
    # System & Monitoring
    # ═══════════════════════════════════════════════════════
    path(
        "health/",
        HealthCheckView.as_view(),
        name="health_check"
    ),
]

# -----------------------------------------------------------
# URL Pattern Summary (for debugging)
# -----------------------------------------------------------
# Uncomment to print all registered URLs during development
# if settings.DEBUG:
#     from django.urls import get_resolver
#     urlconf = get_resolver()
#     print("\n" + "="*80)
#     print("REGISTERED EMPLOYEE API URLS:")
#     print("="*80)
#     for pattern in urlconf.url_patterns:
#         if hasattr(pattern, 'pattern'):
#             print(f"  {pattern.pattern}")
#     print("="*80 + "\n")