# appointments/utils.py
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.urls import reverse
from django.db.models import Sum, Avg, Count
from datetime import datetime, timedelta, time
import logging

# Safe imports with fallbacks
try:
    from twilio.rest import Client as TwilioClient
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    TwilioClient = None

try:
    from celery import shared_task
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    # Fallback decorator
    def shared_task(func):
        return func

logger = logging.getLogger(__name__)

def send_notification(user, notification_type, title, message, appointment=None, action_url=None):
    """
    Send notification to user (database, email, SMS)
    """
    try:
        from .models import Notification
        
        # Create database notification
        notification = Notification.objects.create(
            user=user,
            type=notification_type,
            title=title,
            message=message,
            appointment=appointment,
            action_url=action_url
        )
        
        # Send email if user accepts marketing emails
        try:
            if hasattr(user, 'profile') and user.profile.accepts_marketing:
                send_email_notification(user, title, message, action_url)
        except AttributeError:
            # Profile doesn't exist, send email anyway
            send_email_notification(user, title, message, action_url)
        
        # Send SMS if user accepts SMS and has phone
        try:
            if (hasattr(user, 'profile') and 
                user.profile.accepts_sms and 
                user.profile.phone and 
                TWILIO_AVAILABLE):
                send_sms_notification(user.profile.phone, message)
        except AttributeError:
            # Profile doesn't exist or no phone
            pass
        
        logger.info(f'Notification sent to {user.username}: {title}')
        return notification
        
    except Exception as e:
        logger.error(f'Error sending notification: {e}')
        return None

def send_email_notification(user, title, message, action_url=None):
    """Send email notification"""
    try:
        subject = f"BeautyTime - {title}"
        
        # Create email content
        email_message = f"""
Merhaba {user.get_full_name() or user.username},

{message}
        """
        
        if action_url:
            base_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
            full_url = f"{base_url}{action_url}"
            email_message += f"\n\nDetaylar için: {full_url}"
        
        email_message += """

İyi günler,
BeautyTime Ekibi

Bu e-postayı almak istemiyorsanız, profilinizden bildirim ayarlarınızı değiştirebilirsiniz.
        """
        
        send_mail(
            subject=subject,
            message=email_message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@beautytime.com'),
            recipient_list=[user.email],
            fail_silently=False,
        )
        
        logger.info(f'Email sent to {user.email}')
        
    except Exception as e:
        logger.error(f'Error sending email: {e}')

def send_sms_notification(phone_number, message):
    """Send SMS notification using Twilio"""
    if not TWILIO_AVAILABLE:
        logger.warning('Twilio not available, skipping SMS')
        return
        
    try:
        twilio_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
        twilio_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
        twilio_phone = getattr(settings, 'TWILIO_PHONE_NUMBER', '')
        
        if not all([twilio_sid, twilio_token, twilio_phone]):
            logger.warning('Twilio settings not configured')
            return
        
        client = TwilioClient(twilio_sid, twilio_token)
        
        sms_message = f"BeautyTime: {message}"
        
        message_obj = client.messages.create(
            body=sms_message,
            from_=twilio_phone,
            to=phone_number
        )
        
        logger.info(f'SMS sent to {phone_number}: {message_obj.sid}')
        
    except Exception as e:
        logger.error(f'Error sending SMS: {e}')


def generate_time_slots(employee, date, service, interval_minutes=30):
    """
    Generate available time slots for an employee on a specific date
    """
    from .models import Appointment, BusinessHours, Holiday, EmployeeBreak
    
    # Check if date is a holiday
    if Holiday.objects.filter(date=date).exists():
        return []
    
    # Get business hours for the day
    day_of_week = date.weekday()
    try:
        business_hours = BusinessHours.objects.get(day_of_week=day_of_week)
        if not business_hours.is_open:
            return []
        start_time = business_hours.open_time
        end_time = business_hours.close_time
        break_start = business_hours.break_start
        break_end = business_hours.break_end
    except BusinessHours.DoesNotExist:
        # Default hours if not configured
        start_time = time(9, 0)
        end_time = time(18, 0)
        break_start = None
        break_end = None
    
    # Get employee working hours for this day
    try:
        employee_start, employee_end = employee.get_working_hours(day_of_week)
    except Exception as e:
        logger.error(f"Error getting employee working hours: {str(e)}")
        return []
    
    if not employee_start or not employee_end:
        return []
    
    # Use the more restrictive hours
    actual_start = max(start_time, employee_start)
    actual_end = min(end_time, employee_end)
    
    # Generate time slots
    slots = []
    current_time = datetime.combine(date, actual_start)
    end_datetime = datetime.combine(date, actual_end)
    
    # Subtract service duration from end time to ensure full service can be completed
    end_datetime -= timedelta(minutes=service.duration)
    
    # Current time for comparison
    now = timezone.now()
    
    while current_time <= end_datetime:
        # Skip break time if exists
        if (break_start and break_end and
            break_start <= current_time.time() < break_end):
            current_time += timedelta(minutes=interval_minutes)
            continue
        
        # Make timezone aware for comparison
        try:
            slot_datetime = timezone.make_aware(current_time) if timezone.is_naive(current_time) else current_time
        except Exception as e:
            logger.error(f"Timezone conversion error: {str(e)}")
            current_time += timedelta(minutes=interval_minutes)
            continue
        
        # Only include future time slots (at least 2 hours from now)
        min_booking_time = now + timedelta(hours=2)
        if slot_datetime > min_booking_time:
            # Check if time slot is available
            try:
                if is_time_slot_available(employee, slot_datetime, service.duration):
                    slots.append(current_time.strftime('%H:%M'))
            except Exception as e:
                logger.error(f"Time slot availability check error: {str(e)}")
        
        current_time += timedelta(minutes=interval_minutes)
    
    return slots
def is_time_slot_available(employee, start_time, duration_minutes):
    """
    Check if a time slot is available for an employee
    """
    from .models import Appointment, EmployeeBreak
    
    end_time = start_time + timedelta(minutes=duration_minutes)
    
    # Check for existing appointments
    conflicting_appointments = Appointment.objects.filter(
        employee=employee,
        date_time__lt=end_time,
        end_time__gt=start_time,
        status__in=['pending', 'confirmed', 'in_progress']
    )
    
    if conflicting_appointments.exists():
        return False
    
    # Check for employee breaks
    date = start_time.date()
    employee_breaks = EmployeeBreak.objects.filter(
        employee=employee,
        start_time__date=date,
        start_time__lt=end_time,
        end_time__gt=start_time
    )
    
    if employee_breaks.exists():
        return False
    
    return True

def check_availability(employee, date_time, duration_minutes):
    """
    Check if an employee is available at a specific date and time
    """
    # Check if employee is working on this day
    if not employee.is_available(date_time):
        return False, "Çalışan bu gün çalışmıyor"
    
    # Check if time slot is available
    if not is_time_slot_available(employee, date_time, duration_minutes):
        return False, "Bu saatte başka bir randevu var"
    
    return True, "Müsait"

def get_next_available_slot(employee, service, preferred_date=None):
    """
    Find the next available time slot for an employee and service
    """
    if not preferred_date:
        preferred_date = timezone.now().date() + timedelta(days=1)
    
    # Look for availability in the next 30 days
    for days_ahead in range(30):
        check_date = preferred_date + timedelta(days=days_ahead)
        slots = generate_time_slots(employee, check_date, service)
        
        if slots:
            # Return the first available slot
            first_slot_time = datetime.strptime(slots[0], '%H:%M').time()
            return datetime.combine(check_date, first_slot_time)
    
    return None

def calculate_appointment_end_time(start_time, service):
    """
    Calculate appointment end time based on service duration
    """
    return start_time + timedelta(minutes=service.duration)

def get_business_status():
    """
    Get current business status (open/closed)
    """
    from .models import BusinessHours, Holiday
    
    now = timezone.now()
    today = now.date()
    current_time = now.time()
    day_of_week = now.weekday()
    
    # Check if today is a holiday
    if Holiday.objects.filter(date=today).exists():
        return {
            'is_open': False,
            'status': 'Tatil',
            'message': 'Bugün tatil günümüz'
        }
    
    try:
        business_hours = BusinessHours.objects.get(day_of_week=day_of_week)
        
        if not business_hours.is_open:
            return {
                'is_open': False,
                'status': 'Kapalı',
                'message': 'Bugün kapalıyız'
            }
        
        is_open = business_hours.open_time <= current_time <= business_hours.close_time
        
        # Check if we're in break time
        if (business_hours.break_start and business_hours.break_end and
            business_hours.break_start <= current_time <= business_hours.break_end):
            return {
                'is_open': False,
                'status': 'Mola',
                'message': f'Mola saati: {business_hours.break_start} - {business_hours.break_end}'
            }
        
        if is_open:
            return {
                'is_open': True,
                'status': 'Açık',
                'message': f'Açık: {business_hours.open_time} - {business_hours.close_time}'
            }
        else:
            return {
                'is_open': False,
                'status': 'Kapalı',
                'message': f'Çalışma saatleri: {business_hours.open_time} - {business_hours.close_time}'
            }
    
    except BusinessHours.DoesNotExist:
        # Default business hours
        if 9 <= current_time.hour < 18:
            return {
                'is_open': True,
                'status': 'Açık',
                'message': 'Açık: 09:00 - 18:00'
            }
        else:
            return {
                'is_open': False,
                'status': 'Kapalı',
                'message': 'Çalışma saatleri: 09:00 - 18:00'
            }

def format_appointment_time(date_time):
    """
    Format appointment datetime for display
    """
    if date_time.date() == timezone.now().date():
        return f"Bugün {date_time.strftime('%H:%M')}"
    elif date_time.date() == timezone.now().date() + timedelta(days=1):
        return f"Yarın {date_time.strftime('%H:%M')}"
    else:
        return date_time.strftime('%d %B %Y, %H:%M')

def get_appointment_color(status):
    """
    Get color for appointment status
    """
    color_map = {
        'pending': '#ffc107',      # Yellow
        'confirmed': '#28a745',    # Green
        'in_progress': '#17a2b8',  # Cyan
        'completed': '#6c757d',    # Gray
        'cancelled': '#dc3545',    # Red
        'no_show': '#fd7e14',      # Orange
    }
    return color_map.get(status, '#6c757d')

def validate_appointment_data(service, employee, date_time, user=None):
    """
    Validate appointment data before creation
    """
    errors = []
    
    # Check if service is active
    if not service.is_active:
        errors.append("Seçilen hizmet aktif değil.")
    
    # Check if employee is active
    if not employee.is_active:
        errors.append("Seçilen çalışan aktif değil.")
    
    # Check if employee can provide this service
    if not employee.services.filter(id=service.id).exists():
        errors.append("Seçilen çalışan bu hizmeti sunmuyor.")
    
    # Check if datetime is in the future
    if date_time <= timezone.now():
        errors.append("Randevu tarihi gelecekte olmalıdır.")
    
    # Check minimum advance booking
    min_advance = timezone.now() + timedelta(hours=2)
    if date_time <= min_advance:
        errors.append("Randevu en erken 2 saat sonraya alınabilir.")
    
    # Check maximum advance booking
    max_advance = timezone.now() + timedelta(days=service.max_advance_booking_days)
    if date_time >= max_advance:
        errors.append(f"Randevu en fazla {service.max_advance_booking_days} gün sonraya alınabilir.")
    
    # Check employee availability
    if not employee.is_available(date_time):
        errors.append("Çalışan seçilen tarih ve saatte müsait değil.")
    
    # Check for conflicts
    is_available, message = check_availability(employee, date_time, service.duration)
    if not is_available:
        errors.append(message)
    
    return errors

def send_appointment_reminders():
    """
    Send appointment reminders (to be used in Celery tasks)
    """
    from .models import Appointment
    
    now = timezone.now()
    
    # 24-hour reminders
    reminder_24h = now + timedelta(hours=24)
    appointments_24h = Appointment.objects.filter(
        date_time__range=[reminder_24h - timedelta(minutes=30), reminder_24h + timedelta(minutes=30)],
        status='confirmed',
        reminder_sent_24h=False
    ).select_related('user', 'service', 'employee')
    
    for appointment in appointments_24h:
        send_notification(
            user=appointment.user,
            notification_type='appointment_reminder',
            title='Randevu Hatırlatması - 24 Saat',
            message=f'Yarın {appointment.date_time.strftime("%H:%M")} saatinde {appointment.service.name} randevunuz var.',
            appointment=appointment,
            action_url=reverse('appointment_detail', kwargs={'uuid': appointment.uuid})
        )
        appointment.reminder_sent_24h = True
        appointment.save(update_fields=['reminder_sent_24h'])
    
    # 2-hour reminders
    reminder_2h = now + timedelta(hours=2)
    appointments_2h = Appointment.objects.filter(
        date_time__range=[reminder_2h - timedelta(minutes=15), reminder_2h + timedelta(minutes=15)],
        status='confirmed',
        reminder_sent_2h=False
    ).select_related('user', 'service', 'employee')
    
    for appointment in appointments_2h:
        send_notification(
            user=appointment.user,
            notification_type='appointment_reminder',
            title='Randevu Hatırlatması - 2 Saat',
            message=f'2 saat sonra ({appointment.date_time.strftime("%H:%M")}) randevunuz var. Lütfen zamanında gelin.',
            appointment=appointment,
            action_url=reverse('appointment_detail', kwargs={'uuid': appointment.uuid})
        )
        appointment.reminder_sent_2h = True
        appointment.save(update_fields=['reminder_sent_2h'])
    
    logger.info(f'Sent {len(appointments_24h)} 24h reminders and {len(appointments_2h)} 2h reminders')

def generate_appointment_report(start_date, end_date):
    """
    Generate appointment statistics report
    """
    from .models import Appointment
    from django.db.models import Count, Sum, Avg
    
    appointments = Appointment.objects.filter(
        date_time__date__range=[start_date, end_date]
    )
    
    # Basic statistics
    total_appointments = appointments.count()
    status_breakdown = appointments.values('status').annotate(count=Count('status'))
    
    # Revenue statistics
    completed_appointments = appointments.filter(status='completed')
    total_revenue = completed_appointments.aggregate(Sum('final_price'))['final_price__sum'] or 0
    average_appointment_value = completed_appointments.aggregate(Avg('final_price'))['final_price__avg'] or 0
    
    # Service statistics
    service_stats = appointments.values(
        'service__name'
    ).annotate(
        count=Count('service'),
        revenue=Sum('final_price')
    ).order_by('-count')
    
    # Employee statistics
    employee_stats = appointments.values(
        'employee__name'
    ).annotate(
        count=Count('employee'),
        revenue=Sum('final_price')
    ).order_by('-count')
    
    # Daily breakdown
    daily_stats = appointments.extra(
        select={'day': 'date(date_time)'}
    ).values('day').annotate(
        count=Count('id'),
        revenue=Sum('final_price')
    ).order_by('day')
    
    return {
        'period': {'start': start_date, 'end': end_date},
        'total_appointments': total_appointments,
        'status_breakdown': status_breakdown,
        'total_revenue': total_revenue,
        'average_appointment_value': average_appointment_value,
        'service_stats': service_stats,
        'employee_stats': employee_stats,
        'daily_stats': daily_stats,
    }

def clean_old_notifications():
    """
    Clean old notifications (to be used in Celery tasks)
    """
    from .models import Notification
    
    # Delete notifications older than 90 days
    cutoff_date = timezone.now() - timedelta(days=90)
    deleted_count = Notification.objects.filter(
        created_at__lt=cutoff_date
    ).delete()[0]
    
    logger.info(f'Deleted {deleted_count} old notifications')
    return deleted_count

def backup_database():
    """
    Create database backup (basic implementation)
    """
    import os
    from django.core.management import call_command
    from io import StringIO
    
    try:
        backup_dir = '/tmp/backups'
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f'{backup_dir}/backup_{timestamp}.json'
        
        with open(backup_file, 'w') as f:
            call_command('dumpdata', stdout=f, exclude=['contenttypes', 'auth.permission'])
        
        logger.info(f'Database backup created: {backup_file}')
        return backup_file
        
    except Exception as e:
        logger.error(f'Error creating database backup: {e}')
        return None

def send_marketing_email(subject, message, user_queryset=None):
    """
    Send marketing emails to users
    """
    from django.contrib.auth.models import User
    
    if user_queryset is None:
        # Send to all users who accept marketing emails
        user_queryset = User.objects.filter(
            is_active=True,
            profile__accepts_marketing=True
        )
    
    sent_count = 0
    failed_count = 0
    
    for user in user_queryset:
        try:
            send_email_notification(user, subject, message)
            sent_count += 1
        except Exception as e:
            logger.error(f'Failed to send marketing email to {user.email}: {e}')
            failed_count += 1
    
    logger.info(f'Marketing email sent to {sent_count} users, {failed_count} failed')
    return {'sent': sent_count, 'failed': failed_count}

def calculate_employee_commission(employee, start_date, end_date, commission_rate=0.30):
    """
    Calculate employee commission for a period
    """
    from .models import Appointment
    
    completed_appointments = Appointment.objects.filter(
        employee=employee,
        status='completed',
        date_time__date__range=[start_date, end_date]
    )
    
    total_revenue = completed_appointments.aggregate(Sum('final_price'))['final_price__sum'] or 0
    commission = total_revenue * commission_rate
    
    return {
        'employee': employee,
        'period': {'start': start_date, 'end': end_date},
        'appointments_count': completed_appointments.count(),
        'total_revenue': total_revenue,
        'commission_rate': commission_rate,
        'commission_amount': commission,
    }

def get_popular_services(days=30):
    """
    Get most popular services in the last N days
    """
    from .models import Appointment
    from django.db.models import Count
    
    start_date = timezone.now() - timedelta(days=days)
    
    popular_services = Appointment.objects.filter(
        date_time__gte=start_date,
        status__in=['completed', 'confirmed']
    ).values(
        'service__name',
        'service__id'
    ).annotate(
        booking_count=Count('service')
    ).order_by('-booking_count')[:10]
    
    return popular_services

def get_customer_lifetime_value(user):
    """
    Calculate customer lifetime value
    """
    from .models import Appointment
    
    completed_appointments = Appointment.objects.filter(
        user=user,
        status='completed'
    )
    
    total_spent = completed_appointments.aggregate(Sum('final_price'))['final_price__sum'] or 0
    appointment_count = completed_appointments.count()
    
    if appointment_count > 0:
        average_appointment_value = total_spent / appointment_count
        
        # Calculate average time between appointments
        if appointment_count > 1:
            first_appointment = completed_appointments.order_by('date_time').first()
            last_appointment = completed_appointments.order_by('date_time').last()
            days_between = (last_appointment.date_time - first_appointment.date_time).days
            
            if days_between > 0:
                average_days_between_appointments = days_between / (appointment_count - 1)
                # Estimate annual frequency
                annual_frequency = 365 / average_days_between_appointments
                estimated_annual_value = average_appointment_value * annual_frequency
            else:
                estimated_annual_value = average_appointment_value
        else:
            estimated_annual_value = average_appointment_value
    else:
        average_appointment_value = 0
        estimated_annual_value = 0
    
    return {
        'total_spent': total_spent,
        'appointment_count': appointment_count,
        'average_appointment_value': average_appointment_value,
        'estimated_annual_value': estimated_annual_value,
    }