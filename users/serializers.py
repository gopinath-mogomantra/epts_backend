# ===============================================
# users/serializers.py
# ===============================================
# Defines:
# - CustomTokenObtainPairSerializer (JWT login)
# - RegisterSerializer (user signup)
# - ChangePasswordSerializer (password update)
# - ProfileSerializer (profile details)
# ===============================================

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
import datetime
from .models import CustomUser
from rest_framework import serializers
from django.contrib.auth.models import User

User = get_user_model()

# =====================================================
# ✅ 1. Custom JWT Token Serializer
# =====================================================
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['email'] = user.email
        token['role'] = getattr(user.role, 'name', None)
        token['first_name'] = user.first_name
        token['last_name'] = user.last_name
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data['user'] = {
            'id': self.user.id,
            'username': self.user.username,
            'email': self.user.email,
            'first_name': self.user.first_name,
            'last_name': self.user.last_name,
            'role': getattr(self.user.role, 'name', None),
        }
        return data

# =====================================================
# ✅ 2. User Registration Serializer
# =====================================================
class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, required=True, validators=[validate_password]
    )
    password2 = serializers.CharField(write_only=True, required=True)
    role = serializers.PrimaryKeyRelatedField(
        queryset=User._meta.get_field('role').remote_field.model.objects.all(),
        required=False
    )
    joining_date = serializers.DateField(required=False)

    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'first_name', 'last_name',
            'emp_id', 'phone', 'role', 'password', 'password2', 'joining_date'
        )
        read_only_fields = ('id',)

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Passwords do not match."})
        return attrs

    def validate_joining_date(self, value):
        # Convert datetime to date, if necessary
        if isinstance(value, datetime.datetime):
            return value.date()
        return value

    def create(self, validated_data):
        validated_data.pop('password2', None)
        password = validated_data.pop('password')
        role = validated_data.pop('role', None)

        user = User(**validated_data)
        if role:
            user.role = role
        user.set_password(password)
        user.save()
        return user
    

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = [
            'id',
            'emp_id',
            'first_name',
            'last_name',
            'email',
            'department',
            'role',
            'joining_date',
        ]

# =====================================================
# ✅ 3. Change Password Serializer
# =====================================================
class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is not correct.")
        return value
    
    def update(self, instance, validated_data):
        # Update the user's password
        instance.set_password(validated_data['new_password'])
        instance.save()
        return instance


    def create(self, validated_data):
        # Not needed but required by DRF if save() is called on new instance
        raise NotImplementedError("This serializer cannot create new users.")

# =====================================================
# ✅ 4. Profile Serializer
# =====================================================
class ProfileSerializer(serializers.ModelSerializer):
    role = serializers.StringRelatedField()  # Displays role name instead of ID

    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'first_name', 'last_name',
            'emp_id', 'phone', 'role', 'joining_date', 'is_verified'
        )
