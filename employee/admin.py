# ===============================================
# employee/admin.py (Enhanced Version — 01-Nov-2025)
# ===============================================
"""
Django Admin Configuration for Employee Management System

Features:
  ✅ Department management with live employee count & statistics
  ✅ Employee admin with user info (emp_id, email, role, dept)
  ✅ Advanced filtering, search, and bulk actions
  ✅ Role badges and status color coding
  ✅ Inline editing capabilities
  ✅ Custom actions (activate, deactivate, export)
  ✅ Audit trail and logging
  ✅ Performance optimizations
  ✅ CSV export functionality
  ✅ Read-only mode for critical fields
"""
# ===============================================

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.contrib import messages
from django.utils import timezone
import csv
import logging

from .models import Employee, Department

logger = logging.getLogger(__name__)


# =====================================================
# CUSTOM FILTERS
# =====================================================
class ActiveStatusFilter(admin.SimpleListFilter):
    """Filter employees by active/inactive status."""
    
    title = "Employment Status"
    parameter_name = "employment_status"

    def lookups(self, request, model_admin):
        return (
            ("active", "Active Only"),
            ("inactive", "Inactive Only"),
            ("deleted", "Soft Deleted"),
            ("has_team", "Has Team Members"),
        )

    def queryset(self, request, queryset):
        if self.value() == "active":
            return queryset.filter(status="Active", is_deleted=False)
        if self.value() == "inactive":
            return queryset.filter(status="Inactive", is_deleted=False)
        if self.value() == "deleted":
            return queryset.filter(is_deleted=True)
        if self.value() == "has_team":
            return queryset.filter(team_members__isnull=False).distinct()


class DepartmentSizeFilter(admin.SimpleListFilter):
    """Filter departments by employee count."""
    
    title = "Department Size"
    parameter_name = "dept_size"

    def lookups(self, request, model_admin):
        return (
            ("small", "Small (1-10)"),
            ("medium", "Medium (11-50)"),
            ("large", "Large (51-100)"),
            ("xlarge", "Extra Large (100+)"),
            ("empty", "Empty"),
        )

    def queryset(self, request, queryset):
        queryset = queryset.annotate(emp_count=Count("employees"))
        if self.value() == "small":
            return queryset.filter(emp_count__gte=1, emp_count__lte=10)
        if self.value() == "medium":
            return queryset.filter(emp_count__gte=11, emp_count__lte=50)
        if self.value() == "large":
            return queryset.filter(emp_count__gte=51, emp_count__lte=100)
        if self.value() == "xlarge":
            return queryset.filter(emp_count__gt=100)
        if self.value() == "empty":
            return queryset.filter(emp_count=0)


# =====================================================
# INLINE ADMIN CLASSES
# =====================================================
class TeamMemberInline(admin.TabularInline):
    """Display team members inline for managers."""
    
    model = Employee
    fk_name = "manager"
    extra = 0
    can_delete = False
    show_change_link = True
    
    fields = ("user", "designation", "status", "joining_date")
    readonly_fields = ("user", "designation", "status", "joining_date")
    
    verbose_name = "Team Member"
    verbose_name_plural = "Team Members"

    def has_add_permission(self, request, obj=None):
        return False


# =====================================================
# DEPARTMENT ADMIN
# =====================================================
@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    """
    Enhanced admin configuration for Department model.
    
    Features:
      - Live employee count with color coding
      - Bulk activate/deactivate actions
      - Export to CSV
      - Statistics dashboard
      - Employee list link
    """

    list_display = (
        "id",
        "name",
        "code",
        "employee_count_badge",
        "colored_status",
        "view_employees_link",
        "created_at",
        "updated_at",
    )
    
    list_display_links = ("id", "name")
    
    search_fields = ("name", "description", "code")
    
    list_filter = ("is_active", DepartmentSizeFilter, "created_at", "updated_at")
    
    ordering = ("name",)
    
    readonly_fields = (
        "created_at",
        "updated_at",
        "employee_count",
        "active_employee_count",
        "inactive_employee_count",
        "employee_statistics",
    )
    
    fieldsets = (
        ("Basic Information", {
            "fields": ("name", "code", "description", "is_active")
        }),
        ("Statistics", {
            "fields": (
                "employee_count",
                "active_employee_count",
                "inactive_employee_count",
                "employee_statistics",
            ),
            "classes": ("collapse",),
        }),
        ("Metadata", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )
    
    actions = ["activate_departments", "deactivate_departments", "export_to_csv"]

    # --------------------------------------------
    # Display Methods
    # --------------------------------------------
    def employee_count_badge(self, obj):
        """Display employee count with color-coded badge."""
        count = obj.employees.filter(status="Active", is_deleted=False).count()
        
        # Color coding based on size
        if count == 0:
            color = "#6c757d"  # Gray
            icon = "⚪"
        elif count <= 10:
            color = "#28a745"  # Green
            icon = "🟢"
        elif count <= 50:
            color = "#ffc107"  # Yellow
            icon = "🟡"
        else:
            color = "#dc3545"  # Red
            icon = "🔴"
        
        return format_html(
            '<span style="background-color:{}; color:white; padding:4px 10px; '
            'border-radius:12px; font-weight:bold;">{} {}</span>',
            color, icon, count
        )
    
    employee_count_badge.short_description = "Active Employees"
    employee_count_badge.admin_order_field = "employee_count"

    def colored_status(self, obj):
        """Show green if active, red if inactive."""
        if obj.is_active:
            return format_html(
                '<span style="color:green; font-weight:bold;">✅ Active</span>'
            )
        return format_html(
            '<span style="color:red; font-weight:bold;">❌ Inactive</span>'
        )
    
    colored_status.short_description = "Status"
    colored_status.admin_order_field = "is_active"

    def view_employees_link(self, obj):
        """Link to view all employees in this department."""
        count = obj.employees.filter(is_deleted=False).count()
        if count == 0:
            return format_html('<span style="color:#999;">No employees</span>')
        
        url = reverse("admin:employee_employee_changelist")
        url += f"?department__id__exact={obj.id}"
        
        return format_html(
            '<a href="{}" style="color:#007bff; text-decoration:none;">'
            '📋 View {} employee{}</a>',
            url, count, "s" if count != 1 else ""
        )
    
    view_employees_link.short_description = "Employees"

    def active_employee_count(self, obj):
        """Count of active employees."""
        return obj.employees.filter(status="Active", is_deleted=False).count()
    
    active_employee_count.short_description = "Active Employees"

    def inactive_employee_count(self, obj):
        """Count of inactive employees."""
        return obj.employees.filter(status="Inactive", is_deleted=False).count()
    
    inactive_employee_count.short_description = "Inactive Employees"

    def employee_statistics(self, obj):
        """Display detailed employee statistics."""
        employees = obj.employees.filter(is_deleted=False)
        
        stats = {
            "Total": employees.count(),
            "Active": employees.filter(status="Active").count(),
            "Inactive": employees.filter(status="Inactive").count(),
            "Admins": employees.filter(user__role="Admin").count(),
            "Managers": employees.filter(user__role="Manager").count(),
            "Employees": employees.filter(user__role="Employee").count(),
        }
        
        html = '<div style="line-height:1.8;">'
        for key, value in stats.items():
            html += f'<strong>{key}:</strong> {value}<br>'
        html += '</div>'
        
        return mark_safe(html)
    
    employee_statistics.short_description = "Employee Breakdown"

    # --------------------------------------------
    # Optimization Hooks
    # --------------------------------------------
    def get_queryset(self, request):
        """Optimize query performance with annotations."""
        qs = super().get_queryset(request)
        return qs.annotate(
            _active_count=Count(
                "employees",
                filter=Q(employees__status="Active", employees__is_deleted=False)
            )
        ).prefetch_related("employees")

    # --------------------------------------------
    # Custom Actions
    # --------------------------------------------
    @admin.action(description="✅ Activate selected departments")
    def activate_departments(self, request, queryset):
        """Bulk activate departments."""
        updated = queryset.update(is_active=True)
        self.message_user(
            request,
            f"✅ Successfully activated {updated} department(s).",
            messages.SUCCESS
        )
        logger.info(f"Departments activated by {request.user.username}: {updated}")

    @admin.action(description="❌ Deactivate selected departments")
    def deactivate_departments(self, request, queryset):
        """Bulk deactivate departments (only if no active employees)."""
        errors = []
        deactivated = 0
        
        for dept in queryset:
            active_count = dept.employees.filter(
                status="Active", is_deleted=False
            ).count()
            
            if active_count > 0:
                errors.append(f"{dept.name} has {active_count} active employee(s)")
            else:
                dept.is_active = False
                dept.save()
                deactivated += 1
        
        if deactivated:
            self.message_user(
                request,
                f"✅ Successfully deactivated {deactivated} department(s).",
                messages.SUCCESS
            )
        
        if errors:
            self.message_user(
                request,
                f"⚠️ Could not deactivate: " + "; ".join(errors[:3]),
                messages.WARNING
            )

    @admin.action(description="📥 Export to CSV")
    def export_to_csv(self, request, queryset):
        """Export departments to CSV file."""
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="departments.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            "ID", "Name", "Code", "Description", "Is Active",
            "Employee Count", "Created At", "Updated At"
        ])
        
        for dept in queryset:
            writer.writerow([
                dept.id,
                dept.name,
                dept.code,
                dept.description,
                "Yes" if dept.is_active else "No",
                dept.employees.filter(status="Active", is_deleted=False).count(),
                dept.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                dept.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
            ])
        
        logger.info(f"Departments exported by {request.user.username}")
        return response


# =====================================================
# EMPLOYEE ADMIN
# =====================================================
@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    """
    Enhanced admin configuration for Employee model.
    
    Features:
      - Rich employee information display
      - Manager hierarchy visualization
      - Team member inline editing
      - Bulk status updates
      - CSV export
      - Advanced filtering
    """

    list_display = (
        "get_emp_id",
        "get_full_name",
        "get_email",
        "department_link",
        "designation",
        "colored_role",
        "colored_status",
        "manager_link",
        "team_count",
        "joining_date",
    )
    
    list_display_links = ("get_emp_id", "get_full_name")
    
    search_fields = (
        "user__emp_id",
        "user__first_name",
        "user__last_name",
        "user__email",
        "designation",
        "contact_number",
    )
    
    list_filter = (
        "department",
        "user__role",
        ActiveStatusFilter,
        "status",
        "joining_date",
        "is_deleted",
    )
    
    ordering = ("-created_at",)
    
    readonly_fields = (
        "created_at",
        "updated_at",
        "get_user_info",
        "get_team_info",
        "get_audit_info",
    )
    
    fieldsets = (
        ("User Information", {
            "fields": ("user", "get_user_info")
        }),
        ("Employment Details", {
            "fields": (
                "department",
                "manager",
                "designation",
                "status",
                "joining_date",
            )
        }),
        ("Contact Information", {
            "fields": ("contact_number", "dob", "gender"),
            "classes": ("collapse",),
        }),
        ("Address", {
            "fields": (
                "address_line1",
                "address_line2",
                "city",
                "state",
                "pincode",
            ),
            "classes": ("collapse",),
        }),
        ("Profile", {
            "fields": (
                "profile_picture",
                "project_name",
                "reporting_manager_name",
            ),
            "classes": ("collapse",),
        }),
        ("Team Information", {
            "fields": ("get_team_info",),
            "classes": ("collapse",),
        }),
        ("Audit Information", {
            "fields": ("get_audit_info", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )
    
    inlines = [TeamMemberInline]
    
    actions = [
        "activate_employees",
        "deactivate_employees",
        "export_to_csv",
    ]
    
    list_per_page = 25

    # --------------------------------------------
    # Display Methods
    # --------------------------------------------
    def get_emp_id(self, obj):
        """Display Employee ID with link."""
        emp_id = getattr(obj.user, "emp_id", "-")
        return format_html(
            '<span style="font-family:monospace; font-weight:bold;">{}</span>',
            emp_id
        )
    
    get_emp_id.short_description = "Employee ID"
    get_emp_id.admin_order_field = "user__emp_id"

    def get_full_name(self, obj):
        """Return full name from linked User."""
        if obj.user:
            full_name = f"{obj.user.first_name} {obj.user.last_name}".strip()
            return full_name or obj.user.username
        return "-"
    
    get_full_name.short_description = "Full Name"
    get_full_name.admin_order_field = "user__first_name"

    def get_email(self, obj):
        """Return linked user's email address."""
        email = getattr(obj.user, "email", "-")
        if email and email != "-":
            return format_html(
                '<a href="mailto:{}" style="color:#007bff;">{}</a>',
                email, email
            )
        return "-"
    
    get_email.short_description = "Email"
    get_email.admin_order_field = "user__email"

    def department_link(self, obj):
        """Link to department detail page."""
        if not obj.department:
            return format_html('<span style="color:#999;">-</span>')
        
        url = reverse("admin:employee_department_change", args=[obj.department.pk])
        return format_html(
            '<a href="{}" style="color:#007bff;">{}</a>',
            url, obj.department.name
        )
    
    department_link.short_description = "Department"
    department_link.admin_order_field = "department__name"

    def colored_role(self, obj):
        """Display role as colored badge for better visibility."""
        role = getattr(obj.user, "role", "Unknown")
        role_config = {
            "Admin": ("#007bff", "👑"),
            "Manager": ("#28a745", "👨‍💼"),
            "Employee": ("#6c757d", "👤"),
        }
        
        color, icon = role_config.get(role, ("#999", "❓"))
        
        return format_html(
            '<span style="background-color:{}; color:white; padding:4px 10px; '
            'border-radius:4px; font-weight:bold;">{} {}</span>',
            color, icon, role
        )
    
    colored_role.short_description = "Role"
    colored_role.admin_order_field = "user__role"

    def colored_status(self, obj):
        """Display status with color coding."""
        if obj.is_deleted:
            return format_html(
                '<span style="color:red; font-weight:bold;">🗑️ Deleted</span>'
            )
        
        if obj.status == "Active":
            return format_html(
                '<span style="color:green; font-weight:bold;">✅ Active</span>'
            )
        
        return format_html(
            '<span style="color:orange; font-weight:bold;">⏸️ Inactive</span>'
        )
    
    colored_status.short_description = "Status"
    colored_status.admin_order_field = "status"

    def manager_link(self, obj):
        """Link to manager's profile."""
        if not obj.manager:
            return format_html('<span style="color:#999;">No Manager</span>')
        
        url = reverse("admin:employee_employee_change", args=[obj.manager.pk])
        manager_name = f"{obj.manager.user.first_name} {obj.manager.user.last_name}".strip()
        
        return format_html(
            '<a href="{}" style="color:#007bff;">👨‍💼 {}</a>',
            url, manager_name or obj.manager.user.username
        )
    
    manager_link.short_description = "Manager"

    def team_count(self, obj):
        """Display count of direct reports."""
        count = obj.team_members.filter(status="Active", is_deleted=False).count()
        
        if count == 0:
            return format_html('<span style="color:#999;">-</span>')
        
        url = reverse("admin:employee_employee_changelist")
        url += f"?manager__id__exact={obj.id}"
        
        return format_html(
            '<a href="{}" style="color:#007bff; font-weight:bold;">👥 {}</a>',
            url, count
        )
    
    team_count.short_description = "Team Size"

    def get_user_info(self, obj):
        """Display detailed user information."""
        if not obj.user:
            return "No user linked"
        
        html = f"""
        <div style="line-height:1.8;">
            <strong>Username:</strong> {obj.user.username}<br>
            <strong>Email:</strong> {obj.user.email}<br>
            <strong>Emp ID:</strong> {obj.user.emp_id}<br>
            <strong>Role:</strong> {obj.user.role}<br>
            <strong>Active:</strong> {'✅ Yes' if obj.user.is_active else '❌ No'}<br>
        </div>
        """
        return mark_safe(html)
    
    get_user_info.short_description = "User Details"

    def get_team_info(self, obj):
        """Display team member information."""
        team = obj.team_members.filter(is_deleted=False).select_related("user")
        
        if not team.exists():
            return "No team members"
        
        html = '<div style="line-height:1.8;">'
        html += f'<strong>Total Team Members:</strong> {team.count()}<br>'
        html += f'<strong>Active:</strong> {team.filter(status="Active").count()}<br>'
        html += f'<strong>Inactive:</strong> {team.filter(status="Inactive").count()}<br>'
        html += '<br><strong>Team Members:</strong><br>'
        
        for member in team[:10]:  # Show first 10
            html += f'• {member.user.emp_id} - {member.user.first_name} {member.user.last_name}<br>'
        
        if team.count() > 10:
            html += f'<em>... and {team.count() - 10} more</em>'
        
        html += '</div>'
        return mark_safe(html)
    
    get_team_info.short_description = "Team Information"

    def get_audit_info(self, obj):
        """Display audit trail information."""
        html = f"""
        <div style="line-height:1.8;">
            <strong>Created:</strong> {obj.created_at.strftime('%Y-%m-%d %H:%M:%S')}<br>
            <strong>Last Updated:</strong> {obj.updated_at.strftime('%Y-%m-%d %H:%M:%S')}<br>
            <strong>Soft Deleted:</strong> {'✅ Yes' if obj.is_deleted else '❌ No'}<br>
            <strong>Deleted At:</strong> {obj.deleted_at.strftime('%Y-%m-%d %H:%M:%S') if obj.deleted_at else 'N/A'}<br>
        </div>
        """
        return mark_safe(html)
    
    get_audit_info.short_description = "Audit Trail"

    # --------------------------------------------
    # Optimization Hooks
    # --------------------------------------------
    def get_queryset(self, request):
        """Optimize query performance for admin list view."""
        qs = super().get_queryset(request)
        return qs.select_related(
            "user",
            "department",
            "manager",
            "manager__user"
        ).prefetch_related("team_members")

    # --------------------------------------------
    # Custom Actions
    # --------------------------------------------
    @admin.action(description="✅ Activate selected employees")
    def activate_employees(self, request, queryset):
        """Bulk activate employees."""
        updated = queryset.update(status="Active")
        self.message_user(
            request,
            f"✅ Successfully activated {updated} employee(s).",
            messages.SUCCESS
        )
        logger.info(f"Employees activated by {request.user.username}: {updated}")

    @admin.action(description="⏸️ Deactivate selected employees")
    def deactivate_employees(self, request, queryset):
        """Bulk deactivate employees."""
        updated = queryset.update(status="Inactive")
        self.message_user(
            request,
            f"⏸️ Successfully deactivated {updated} employee(s).",
            messages.WARNING
        )
        logger.info(f"Employees deactivated by {request.user.username}: {updated}")

    @admin.action(description="📥 Export to CSV")
    def export_to_csv(self, request, queryset):
        """Export employees to CSV file."""
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="employees.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            "Emp ID", "First Name", "Last Name", "Email", "Department",
            "Designation", "Role", "Status", "Manager", "Joining Date",
            "Contact Number", "Created At"
        ])
        
        for emp in queryset.select_related("user", "department", "manager", "manager__user"):
            writer.writerow([
                emp.user.emp_id,
                emp.user.first_name,
                emp.user.last_name,
                emp.user.email,
                emp.department.name if emp.department else "-",
                emp.designation or "-",
                emp.user.role,
                emp.status,
                f"{emp.manager.user.first_name} {emp.manager.user.last_name}".strip() if emp.manager else "-",
                emp.joining_date.strftime("%Y-%m-%d") if emp.joining_date else "-",
                emp.contact_number or "-",
                emp.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            ])
        
        logger.info(f"Employees exported by {request.user.username}: {queryset.count()} records")
        return response

    # --------------------------------------------
    # Custom Save Logic
    # --------------------------------------------
    def save_model(self, request, obj, form, change):
        """Custom save logic with admin audit logging."""
        super().save_model(request, obj, form, change)
        emp_id = getattr(obj.user, "emp_id", "N/A")
        
        if change:
            self.message_user(
                request,
                f"✅ Employee '{emp_id}' updated successfully.",
                messages.SUCCESS
            )
            logger.info(f"Employee {emp_id} updated by {request.user.username}")
        else:
            self.message_user(
                request,
                f"✅ Employee '{emp_id}' added successfully.",
                messages.SUCCESS
            )
            logger.info(f"Employee {emp_id} created by {request.user.username}")

    def delete_model(self, request, obj):
        """Custom delete logic with logging."""
        emp_id = getattr(obj.user, "emp_id", "N/A")
        super().delete_model(request, obj)
        
        self.message_user(
            request,
            f"🗑️ Employee '{emp_id}' deleted successfully.",
            messages.WARNING
        )
        logger.warning(f"Employee {emp_id} deleted by {request.user.username}")


# =====================================================
# ADMIN SITE CUSTOMIZATION
# =====================================================
admin.site.site_header = "Employee Management System"
admin.site.site_title = "EMS Admin"
admin.site.index_title = "Welcome to Employee Management System"