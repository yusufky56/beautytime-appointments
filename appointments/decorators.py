# appointments/decorators.py
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps
import logging
from django.shortcuts import render, redirect, get_object_or_404

logger = logging.getLogger(__name__)

def staff_required(function=None, redirect_field_name='next', login_url='login'):
    """
    Decorator for views that checks that the user is staff member.
    """
    def check_staff(user):
        return user.is_active and user.is_staff
    
    actual_decorator = user_passes_test(
        check_staff,
        login_url=login_url,
        redirect_field_name=redirect_field_name
    )
    
    if function:
        return actual_decorator(function)
    return actual_decorator

def superuser_required(function=None, redirect_field_name='next', login_url='login'):
    """
    Decorator for views that checks that the user is superuser.
    """
    def check_superuser(user):
        return user.is_active and user.is_superuser
    
    actual_decorator = user_passes_test(
        check_superuser,
        login_url=login_url,
        redirect_field_name=redirect_field_name
    )
    
    if function:
        return actual_decorator(function)
    return actual_decorator

def appointment_owner_required(view_func):
    """
    Decorator that checks if user owns the appointment
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        from .models import Appointment
        
        # Get appointment UUID from kwargs
        appointment_uuid = kwargs.get('uuid')
        if not appointment_uuid:
            raise PermissionDenied("Appointment UUID required")
        
        try:
            appointment = Appointment.objects.get(uuid=appointment_uuid)
            if appointment.user != request.user and not request.user.is_staff:
                logger.warning(f'User {request.user.username} tried to access appointment {appointment_uuid} without permission')
                raise PermissionDenied("You don't have permission to access this appointment")
        except Appointment.DoesNotExist:
            raise PermissionDenied("Appointment not found")
        
        return view_func(request, *args, **kwargs)
    
    return wrapper

def business_hours_required(view_func):
    """
    Decorator that checks if business is open
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        from .utils import get_business_status
        
        # Allow staff to access even when closed
        if request.user.is_staff:
            return view_func(request, *args, **kwargs)
        
        business_status = get_business_status()
        if not business_status['is_open']:
            messages.warning(request, f"Şu anda kapalıyız. {business_status['message']}")
            return redirect('home')
        
        return view_func(request, *args, **kwargs)
    
    return wrapper

def rate_limit(max_requests=10, window_minutes=1):
    """
    Simple rate limiting decorator
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            from django.core.cache import cache
            from django.utils import timezone
            
            # Create cache key based on user or IP
            if request.user.is_authenticated:
                cache_key = f"rate_limit_user_{request.user.id}_{view_func.__name__}"
            else:
                cache_key = f"rate_limit_ip_{request.META.get('REMOTE_ADDR')}_{view_func.__name__}"
            
            # Get current request count
            current_requests = cache.get(cache_key, 0)
            
            if current_requests >= max_requests:
                logger.warning(f'Rate limit exceeded for {cache_key}')
                messages.error(request, f'Çok fazla istek gönderdiniz. {window_minutes} dakika sonra tekrar deneyin.')
                return redirect('home')
            
            # Increment counter
            cache.set(cache_key, current_requests + 1, window_minutes * 60)
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator

def verified_email_required(view_func):
    """
    Decorator that checks if user's email is verified
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        # Skip check for staff users
        if request.user.is_staff:
            return view_func(request, *args, **kwargs)
        
        # Check if email is verified (if using django-allauth)
        if hasattr(request.user, 'emailaddress_set'):
            verified_emails = request.user.emailaddress_set.filter(verified=True)
            if not verified_emails.exists():
                messages.warning(request, 'E-posta adresinizi doğrulayın.')
                return redirect('account_email_verification_sent')
        
        return view_func(request, *args, **kwargs)
    
    return wrapper

def profile_complete_required(view_func):
    """
    Decorator that checks if user profile is complete
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        try:
            profile = request.user.profile
            # Check if required fields are filled
            if not profile.phone:
                messages.info(request, 'Lütfen profilinizi tamamlayın.')
                return redirect('profile_edit')
        except:
            # Profile doesn't exist, create one
            from .models import CustomerProfile
            CustomerProfile.objects.create(user=request.user)
            messages.info(request, 'Lütfen profilinizi tamamlayın.')
            return redirect('profile_edit')
        
        return view_func(request, *args, **kwargs)
    
    return wrapper

def ajax_required(view_func):
    """
    Decorator that ensures the request is AJAX
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            raise PermissionDenied("This view requires AJAX request")
        
        return view_func(request, *args, **kwargs)
    
    return wrapper

def json_response_required(view_func):
    """
    Decorator for API views that ensures JSON response
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        from django.http import JsonResponse
        
        try:
            return view_func(request, *args, **kwargs)
        except Exception as e:
            logger.error(f'Error in API view {view_func.__name__}: {e}')
            return JsonResponse({'error': 'Internal server error'}, status=500)
    
    return wrapper

def log_user_action(action_name):
    """
    Decorator that logs user actions
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if request.user.is_authenticated:
                logger.info(f'User {request.user.username} performed action: {action_name}')
            else:
                logger.info(f'Anonymous user performed action: {action_name}')
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator

def maintenance_mode_check(view_func):
    """
    Decorator that checks if site is in maintenance mode
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        from django.conf import settings
        
        # Allow staff to access during maintenance
        if request.user.is_staff:
            return view_func(request, *args, **kwargs)
        
        if getattr(settings, 'MAINTENANCE_MODE', False):
            return render(request, 'maintenance.html', status=503)
        
        return view_func(request, *args, **kwargs)
    
    return wrapper