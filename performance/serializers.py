# performance/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import PerformanceEvaluation
from employee.models import Department

User = get_user_model()


# ----------------------------
# Nested Serializers (for display)
# ----------------------------
class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = '__all__'
        ref_name = 'PerformanceDepartment'


class SimpleUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'emp_id', 'first_name', 'last_name', 'email']


# ----------------------------
# Main Performance Serializer
# ----------------------------
class PerformanceEvaluationSerializer(serializers.ModelSerializer):
    emp = SimpleUserSerializer(read_only=True)
    manager = SimpleUserSerializer(read_only=True)
    department = DepartmentSerializer(read_only=True)
    evaluation_summary = serializers.SerializerMethodField()

    class Meta:
        model = PerformanceEvaluation
        fields = [
            'id', 'emp', 'department', 'manager',
            'review_date', 'evaluation_period',
            'evaluation_summary', 'total_score', 'remarks',
            'created_at', 'updated_at',
            'communication_skills', 'multitasking', 'team_skills',
            'technical_skills', 'job_knowledge', 'productivity',
            'creativity', 'work_quality', 'professionalism',
            'work_consistency', 'attitude', 'cooperation',
            'dependability', 'attendance', 'punctuality',
        ]

    def get_evaluation_summary(self, obj):
        """
        Return structured summary of each metric for the frontend dashboard.
        """
        metrics = [
            ("Communication Skills", obj.communication_skills),
            ("Multi-tasking Abilities", obj.multitasking),
            ("Team Skills", obj.team_skills),
            ("Technical Skills", obj.technical_skills),
            ("Job Knowledge", obj.job_knowledge),
            ("Productivity", obj.productivity),
            ("Creativity", obj.creativity),
            ("Work Quality", obj.work_quality),
            ("Professionalism", obj.professionalism),
            ("Work Consistency", obj.work_consistency),
            ("Attitude", obj.attitude),
            ("Cooperation", obj.cooperation),
            ("Dependability", obj.dependability),
            ("Attendance", obj.attendance),
            ("Punctuality", obj.punctuality),
        ]
        return [{"measurement": name, "score": score} for name, score in metrics]


# ----------------------------
# Serializer for POST/PUT
# ----------------------------
class PerformanceCreateUpdateSerializer(serializers.ModelSerializer):
    emp = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    manager = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False, allow_null=True)
    department = serializers.PrimaryKeyRelatedField(queryset=Department.objects.all(), required=False, allow_null=True)

    class Meta:
        model = PerformanceEvaluation
        fields = [
            'id', 'emp', 'department', 'manager',
            'review_date', 'evaluation_period',
            'communication_skills', 'multitasking', 'team_skills',
            'technical_skills', 'job_knowledge', 'productivity',
            'creativity', 'work_quality', 'professionalism',
            'work_consistency', 'attitude', 'cooperation',
            'dependability', 'attendance', 'punctuality',
            'remarks'
        ]

    def validate(self, data):
        """
        Ensure all scores are between 0 and 100.
        """
        metric_fields = [
            'communication_skills', 'multitasking', 'team_skills', 'technical_skills',
            'job_knowledge', 'productivity', 'creativity', 'work_quality',
            'professionalism', 'work_consistency', 'attitude', 'cooperation',
            'dependability', 'attendance', 'punctuality'
        ]
        for field in metric_fields:
            value = data.get(field, 0)
            if not (0 <= int(value) <= 100):
                raise serializers.ValidationError({field: "Score must be between 0 and 100."})
        return data
