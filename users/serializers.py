from rest_framework import serializers
from users.models import User

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role', 'department', 'subcounty', 'assigned_nccg', 'full_name', 'avatar_url', 'status', 'last_login_at', 'date_joined', 'created_by']
        read_only_fields = ['id', 'date_joined', 'last_login_at', 'created_by']

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    class Meta:
        model = User
        fields = ['email', 'password', 'full_name', 'role', 'department', 'subcounty', 'assigned_nccg']

    def create(self, validated_data):
        email = validated_data['email']
        username = email  # use email as username
        request = self.context.get('request')
        created_by = request.user if request and request.user.is_authenticated else None

        user = User.objects.create_user(
            username=username,
            email=email,
            password=validated_data['password'],
            full_name=validated_data.get('full_name', ''),
            role=validated_data.get('role', 'pho'),
            department=validated_data.get('department', ''),
            subcounty=validated_data.get('subcounty', ''),
            assigned_nccg=validated_data.get('assigned_nccg', None),
            created_by=created_by
        )
        return user
