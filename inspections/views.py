from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from inspections.models import Business, Inspection, ReportVerificationLog, SystemActivityLog, ClientErrorLog
from inspections.serializers import BusinessSerializer, InspectionSerializer, ReportVerificationLogSerializer, SystemActivityLogSerializer, ClientErrorLogSerializer

class BusinessViewSet(viewsets.ModelViewSet):
    queryset = Business.objects.all()
    serializer_class = BusinessSerializer
    permission_classes = [permissions.IsAuthenticated]
    search_fields = ['business_name', 'permit_no', 'subcounty_name', 'ward_name']

    def get_queryset(self):
        user = self.request.user
        # Admins and Super Admins see everything
        if user.role in ('super_admin', 'finance_manager'):
            return Business.objects.all()
            
        if user.role in ('pho', 'nccg_inspector'):
            if not user.subcounty:
                # Security: If no subcounty set, they see NOTHING
                return Business.objects.none()
            return Business.objects.filter(subcounty_name__iexact=user.subcounty)
            
        # Default fallback for other roles: see nothing by default for security
        return Business.objects.none()

import django_filters
from django.db.models import Q

class InspectionFilter(django_filters.FilterSet):
    is_alert = django_filters.BooleanFilter(method='filter_is_alert')
    is_action_required = django_filters.BooleanFilter(method='filter_is_action_required')
    inspection_date = django_filters.DateFromToRangeFilter()
    inspection_date__date = django_filters.DateFilter(field_name='inspection_date', lookup_expr='date')

    class Meta:
        model = Inspection
        fields = {
            'is_paid': ['exact'],
            'payment_status': ['exact', 'in'],
            'payment_method': ['exact', 'in'],
            'approval_status': ['exact', 'in'],
            'status': ['exact', 'in'],
            'inspector': ['exact', 'in'],
            'is_draft': ['exact'],
            'inspection_date': ['exact', 'date', 'gte', 'lte'],
            'updated_at': ['exact', 'date', 'gte', 'lte'],
            'business__subcounty_name': ['exact', 'in', 'icontains'],
            'business__business_name': ['icontains'],
        }

    def filter_is_alert(self, queryset, name, value):
        if value:
            return queryset.filter(Q(payment_status='flagged') | Q(approval_status='pending'))
        return queryset

    def filter_is_action_required(self, queryset, name, value):
        if value:
            return queryset.filter(Q(payment_status='flagged') | Q(approval_status='declined'))
        return queryset

class InspectionViewSet(viewsets.ModelViewSet):
    queryset = Inspection.objects.all()
    serializer_class = InspectionSerializer
    filterset_class = InspectionFilter
    search_fields = ['payment_ref', 'business__business_name']
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.role == 'super_admin':
            return Inspection.objects.all()
        if user.role == 'admin':
            from django.db.models import Q
            return Inspection.objects.filter(Q(inspector__created_by=user) | Q(inspector=user))
        if user.role == 'nccg_inspector':
            # Lock to own subcounty
            if user.subcounty:
                return Inspection.objects.filter(business__subcounty_name=user.subcounty)
            return Inspection.objects.none()
        if user.role == 'pho':
            # PHOs see their own inspections only (subcounty enforced at business lookup level)
            return Inspection.objects.filter(inspector=user)
        if user.role == 'finance_manager':
            # Finance managers manage payments globally
            return Inspection.objects.all()
        return Inspection.objects.filter(inspector=user)

    def perform_create(self, serializer):
        serializer.save(inspector=self.request.user)

    def partial_update(self, request, *args, **kwargs):
        from .utils import log_activity
        instance = self.get_object()
        old_status = instance.approval_status
        old_pay_status = instance.payment_status
        
        response = super().partial_update(request, *args, **kwargs)
        
        new_status = response.data.get('approval_status', old_status)
        new_pay_status = response.data.get('payment_status', old_pay_status)
        
        if old_status != new_status or old_pay_status != new_pay_status:
            log_activity(request.user, 'INSPECTION_STATUS_CHANGE', {
                'inspection_id': str(instance.id),
                'business_name': instance.business.business_name if instance.business else "Unknown Business",
                'old_approval': old_status,
                'new_approval': new_status,
                'old_payment': old_pay_status,
                'new_payment': new_pay_status
            })
            
        return response

    @action(detail=False, methods=['GET'], permission_classes=[permissions.AllowAny], url_path='subcounties')
    def list_subcounties(self, request):
        subcounties = list(
            Business.objects.exclude(subcounty_name__isnull=True)
            .exclude(subcounty_name='')
            .values_list('subcounty_name', flat=True)
            .distinct()
            .order_by('subcounty_name')
        )
        return Response(subcounties)

    @action(detail=False, methods=['GET'], permission_classes=[permissions.AllowAny], url_path='verify/(?P<report_id>[^/.]+)')
    def verify_report_public(self, request, report_id=None):
        """Replaces Supabase RPC `verify_report_public`"""
        try:
            inspection = Inspection.objects.get(id=report_id)
            # Log the request
            ReportVerificationLog.objects.create(
                report_id=report_id,
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
            data = InspectionSerializer(inspection).data
            # In supabase it might join businesses
            if inspection.business:
                data['businesses'] = BusinessSerializer(inspection.business).data
            return Response(data)
        except Inspection.DoesNotExist:
            return Response({'error': 'Inspection not found'}, status=status.HTTP_404_NOT_FOUND)

class ReportVerificationLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ReportVerificationLog.objects.all()
    serializer_class = ReportVerificationLogSerializer
    permission_classes = [permissions.IsAuthenticated]

class SystemActivityLogViewSet(viewsets.ModelViewSet):
    queryset = SystemActivityLog.objects.all().order_by('-created_at')
    serializer_class = SystemActivityLogSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        # Optimization: Batch fetch related user names for the current page
        # This prevents 100+ separate queries per page load
        logs = self.get_queryset()
        # Use pagination bounds if available
        try:
            page = self.paginate_queryset(logs)
            target_logs = page if page is not None else logs
        except:
            target_logs = logs

        uids = {log.user_id for log in target_logs if log.user_id}
        if uids:
            from users.models import User
            users_map = {
                str(u.id): u.full_name or u.username 
                for u in User.objects.filter(id__in=uids)
            }
            context['user_names'] = users_map
        return context

class ClientErrorLogViewSet(viewsets.ModelViewSet):
    queryset = ClientErrorLog.objects.all()
    serializer_class = ClientErrorLogSerializer
    
    def get_permissions(self):
        if self.action == 'create':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]
