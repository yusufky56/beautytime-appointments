# appointments/context_processors.py
from django.conf import settings
from django.utils import timezone
from .models import Notification, Service, Employee
from .utils import get_business_status

def business_info(request):
    """
    Add business information to all templates
    """
    business_settings = getattr(settings, 'BUSINESS_SETTINGS', {})
    
    return {
        'business_name': business_settings.get('NAME', 'BeautyTime'),
        'business_phone': business_settings.get('PHONE', '+90 (555) 123 45 67'),
        'business_email': business_settings.get('EMAIL', 'info@beautytime.com'),
        'business_address': business_settings.get('ADDRESS', ''),
        'business_social_media': business_settings.get('SOCIAL_MEDIA', {}),
        'business_working_hours': business_settings.get('WORKING_HOURS', {}),
        'business_status': get_business_status(),
    }

def notification_count(request):
    """
    Add unread notification count to all templates
    """
    if request.user.is_authenticated:
        unread_count = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).count()
        
        return {
            'unread_notifications_count': min(unread_count, 99),  # Cap at 99
        }
    
    return {
        'unread_notifications_count': 0,
    }

def site_statistics(request):
    """
    Add site statistics to templates
    """
    return {
        'total_services': Service.objects.filter(is_active=True).count(),
        'total_employees': Employee.objects.filter(is_active=True).count(),
        'current_year': timezone.now().year,
    }

def user_preferences(request):
    """
    Add user preferences to templates
    """
    if request.user.is_authenticated:
        try:
            profile = request.user.profile
            return {
                'user_profile': profile,
                'user_accepts_marketing': profile.accepts_marketing,
                'user_accepts_sms': profile.accepts_sms,
                'user_preferred_employee': profile.preferred_employee,
            }
        except:
            return {
                'user_profile': None,
                'user_accepts_marketing': True,
                'user_accepts_sms': True,
                'user_preferred_employee': None,
            }
    
    return {}

def app_settings(request):
    """
    Add application settings to templates
    """
    return {
        'app_version': '1.0.0',
        'debug_mode': settings.DEBUG,
        'google_analytics_id': getattr(settings, 'GOOGLE_ANALYTICS_ID', ''),
        'facebook_pixel_id': getattr(settings, 'FACEBOOK_PIXEL_ID', ''),
        'site_url': getattr(settings, 'SITE_URL', 'http://localhost:8000'),
        'contact_email': getattr(settings, 'CONTACT_EMAIL', 'info@beautytime.com'),
        'support_phone': getattr(settings, 'SUPPORT_PHONE', '+90 555 123 45 67'),
    }