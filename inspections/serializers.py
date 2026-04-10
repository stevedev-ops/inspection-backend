from rest_framework import serializers
from inspections.models import Business, Inspection, ReportVerificationLog, SystemActivityLog, ClientErrorLog

class BusinessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Business
        fields = '__all__'

class InspectionSerializer(serializers.ModelSerializer):
    businesses = BusinessSerializer(source='business', read_only=True)
    business_id = serializers.PrimaryKeyRelatedField(
        source='business', 
        queryset=Business.objects.all(), 
        required=False, 
        allow_null=True
    )
    gps_coordinates = serializers.SerializerMethodField()

    class Meta:
        model = Inspection
        fields = '__all__'
    
    def get_gps_coordinates(self, obj):
        if obj.business:
            return {
                'lat': obj.business.location_lat,
                'lng': obj.business.location_lng
            }
        return None

class ReportVerificationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportVerificationLog
        fields = '__all__'

class SystemActivityLogSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    action_display = serializers.CharField(source='action', read_only=True)

    class Meta:
        model = SystemActivityLog
        fields = ['id', 'user_id', 'user_name', 'action', 'action_display', 'details', 'created_at']

    def get_user_name(self, obj):
        if not obj.user_id:
            return 'System'
            
        # Optimization: Try to get from pre-fetched context map first
        user_names = self.context.get('user_names', {})
        uid_str = str(obj.user_id)
        if uid_str in user_names:
            return user_names[uid_str]

        try:
            from users.models import User
            user = User.objects.get(id=obj.user_id)
            return user.full_name or user.username
        except:
            return f"User({uid_str[:8]})"

class ClientErrorLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientErrorLog
        fields = '__all__'
