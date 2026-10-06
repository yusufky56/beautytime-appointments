# appointments/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import views as auth_views
from django.contrib.auth import login, authenticate
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.views import generic
from django.views.decorators.http import require_http_methods, require_POST
from django.utils import timezone
from django.http import JsonResponse, HttpResponse, Http404, HttpResponseRedirect
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg, Sum
from django.db import transaction
from django.core.mail import send_mail
from django.conf import settings
from datetime import datetime, timedelta, time
import json
import logging
import uuid

from .models import (
    Appointment, Service, Employee, Notification, Review,
    CustomerProfile, ServiceCategory, BusinessHours, Holiday,
    AppointmentStatusHistory, ContactMessage, FAQ
)
from .forms import (
    CustomUserCreationForm, CustomAuthenticationForm, AppointmentForm,
    AppointmentRescheduleForm, ReviewForm, CustomerProfileForm,
    ContactForm, AppointmentSearchForm, QuickAppointmentForm
)
from .utils import (
    send_notification, generate_time_slots, check_availability,
    is_time_slot_available, get_business_status
)
from .decorators import staff_required

logger = logging.getLogger(__name__)

# --- Authentication Views ---
class CustomLoginView(auth_views.LoginView):
    form_class = CustomAuthenticationForm
    template_name = 'registration/login.html'
    redirect_authenticated_user = True

    def get_success_url(self):
        url = self.get_redirect_url()
        messages.success(self.request, f'Hoş geldiniz, {self.request.user.get_full_name() or self.request.user.username}!')
        return url or reverse_lazy('dashboard')

    def form_invalid(self, form):
        logger.warning(f"Login form invalid: {form.errors.as_json()}")
        
        for field, errors in form.errors.items():
            for error in errors:
                if field == '__all__':
                    messages.error(self.request, error)
                else:
                    field_label = form.fields.get(field, {}).label or field
                    messages.error(self.request, f"{field_label}: {error}")
        
        return super().form_invalid(form)


class CustomLogoutView(auth_views.LogoutView):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            messages.success(request, 'Başarıyla çıkış yaptınız.')
        return super().dispatch(request, *args, **kwargs)


class SignUpView(generic.CreateView):
    form_class = CustomUserCreationForm
    template_name = 'registration/register.html'
    success_url = reverse_lazy('login')

    def form_valid(self, form):
        user = form.save()
        
        try:
            send_notification(
                user=user,
                notification_type='system',
                title='BeautyTime\'a Hoş Geldiniz!',
                message=f'Merhaba {user.get_full_name() or user.username}! Hesabınız başarıyla oluşturuldu.',
                action_url=reverse('appointment_create')
            )
        except Exception as e:
            logger.error(f"Welcome notification could not be sent for {user.username}: {e}")

        messages.success(self.request, 'Hesabınız başarıyla oluşturuldu! Lütfen giriş yapın.')
        logger.info(f'New user registered: {user.username}')
        
        return redirect(self.success_url)

    def form_invalid(self, form):
        logger.warning(f"Registration form invalid: {form.errors.as_json()}")
        
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(self.request, f"{field}: {error}")
        
        return super().form_invalid(form)


# --- Main Views ---
def home(request):
    total_appointments = Appointment.objects.count()
    total_services = Service.objects.filter(is_active=True).count()
    total_employees = Employee.objects.filter(is_active=True).count()
    featured_services = Service.objects.filter(is_active=True).select_related('category').order_by('?')[:6]
    recent_reviews = Review.objects.filter(is_approved=True).select_related('user', 'service', 'employee').order_by('-created_at')[:3]

    context = {
        'total_appointments': total_appointments,
        'total_services': total_services,
        'total_employees': total_employees,
        'featured_services': featured_services,
        'recent_reviews': recent_reviews,
    }
    
    if request.user.is_authenticated:
        upcoming_appointments = Appointment.objects.filter(
            user=request.user,
            date_time__gte=timezone.now(),
            status__in=['pending', 'confirmed']
        ).select_related('service', 'employee').order_by('date_time')[:3]
        context['upcoming_appointments'] = upcoming_appointments
    
    return render(request, 'appointments/home.html', context)


@login_required
def dashboard(request):
    user = request.user
    appointments = Appointment.objects.filter(user=user)
    upcoming_appointments = appointments.filter(
        date_time__gte=timezone.now(),
        status__in=['pending', 'confirmed']
    ).select_related('service', 'employee').order_by('date_time')
    recent_completed_appointments = appointments.filter(
        status='completed'
    ).select_related('service', 'employee').order_by('-date_time')[:5]
    notifications_unread = Notification.objects.filter(user=user, is_read=False).order_by('-created_at')[:5]

    try:
        profile = user.profile
    except CustomerProfile.DoesNotExist:
        profile = CustomerProfile.objects.create(user=user)

    stats = {
        'total_appointments': appointments.count(),
        'pending_appointments': appointments.filter(status='pending').count(),
        'confirmed_appointments': appointments.filter(status='confirmed').count(),
        'completed_appointments': appointments.filter(status='completed').count(),
        'total_spent': appointments.filter(status='completed').aggregate(Sum('final_price'))['final_price__sum'] or 0,
    }
    
    context = {
        'upcoming_appointments': upcoming_appointments,
        'recent_completed_appointments': recent_completed_appointments,
        'notifications_unread': notifications_unread,
        'profile': profile,
        'stats': stats,
    }
    return render(request, 'appointments/dashboard.html', context)


# --- Appointment Views ---
@login_required
def appointment_list(request):
    base_queryset = Appointment.objects.filter(user=request.user).select_related('service', 'employee').order_by('-date_time')
    
    search_form = AppointmentSearchForm(request.GET or None)
    appointments_filtered = base_queryset

    if search_form.is_valid():
        query = search_form.cleaned_data.get('query')
        service_filter = search_form.cleaned_data.get('service')
        employee_filter = search_form.cleaned_data.get('employee')
        status_filter = search_form.cleaned_data.get('status')
        date_from = search_form.cleaned_data.get('date_from')
        date_to = search_form.cleaned_data.get('date_to')

        if query:
            appointments_filtered = appointments_filtered.filter(
                Q(service__name__icontains=query) |
                Q(employee__name__icontains=query) |
                Q(notes__icontains=query)
            )
        if service_filter:
            appointments_filtered = appointments_filtered.filter(service=service_filter)
        if employee_filter:
            appointments_filtered = appointments_filtered.filter(employee=employee_filter)
        if status_filter:
            appointments_filtered = appointments_filtered.filter(status=status_filter)
        if date_from:
            appointments_filtered = appointments_filtered.filter(date_time__date__gte=date_from)
        if date_to:
            appointments_filtered = appointments_filtered.filter(date_time__date__lte=date_to)

    paginator = Paginator(appointments_filtered, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'search_form': search_form,
        'appointments': page_obj,
    }
    return render(request, 'appointments/appointment_list.html', context)


@login_required
def appointment_create(request):
    if request.method == 'POST':
        form = AppointmentForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                with transaction.atomic():
                    appointment = form.save(commit=False)
                    appointment.user = request.user
                    appointment.date_time = form.cleaned_data['date_time']
                    appointment.uuid = uuid.uuid4()
                    appointment.save()

                    AppointmentStatusHistory.objects.create(
                        appointment=appointment, 
                        new_status='pending',
                        changed_by=request.user, 
                        reason='Randevu oluşturuldu'
                    )
                    
                    send_notification(
                        user=request.user, 
                        notification_type='appointment_created',
                        title='Randevu Oluşturuldu',
                        message=f'{appointment.service.name} için randevunuz {appointment.date_time.strftime("%d.%m.%Y %H:%M")} tarihinde oluşturuldu.',
                        appointment=appointment,
                        action_url=reverse('appointment_detail', kwargs={'uuid': appointment.uuid})
                    )
                    
                    logger.info(f'Appointment created: {appointment.uuid} by {request.user.username}')
                    
                    return JsonResponse({
                        'success': True,
                        'message': 'Randevunuz başarıyla oluşturuldu ve onay bekliyor.',
                        'redirect_url': reverse('appointment_detail', kwargs={'uuid': appointment.uuid})
                    })
            except Exception as e:
                logger.error(f'Error creating appointment: {e}')
                return JsonResponse({'success': False, 'error': f'Sunucu hatası: {str(e)}'}, status=500)
        else:
            logger.warning(f"Appointment creation form invalid: {form.errors.as_json()}")
            return JsonResponse({
                'success': False, 
                'error': 'Lütfen formdaki hataları düzeltin.', 
                'errors': json.loads(form.errors.as_json())
            }, status=400)
    else:
        form = AppointmentForm(user=request.user)

    categories = ServiceCategory.objects.filter(is_active=True, services__is_active=True).distinct().prefetch_related('services')
    context = {'form': form, 'categories': categories}
    return render(request, 'appointments/appointment_create.html', context)


@login_required
def appointment_detail(request, uuid):
    appointment = get_object_or_404(
        Appointment.objects.select_related('service', 'employee', 'user'),
        uuid=uuid,
        user=request.user
    )
    status_history = appointment.status_history.all().order_by('-created_at')
    
    try:
        review = appointment.review
    except Review.DoesNotExist:
        review = None

    context = {
        'appointment': appointment,
        'status_history': status_history,
        'review': review,
        'can_cancel': appointment.can_be_cancelled(),
        'can_reschedule': appointment.can_be_rescheduled(),
        'can_review': appointment.status == 'completed' and not review,
    }
    return render(request, 'appointments/appointment_detail.html', context)


@login_required
@require_POST
def appointment_cancel(request, uuid):
    appointment = get_object_or_404(Appointment, uuid=uuid, user=request.user)

    if not appointment.can_be_cancelled():
        messages.error(request, 'Bu randevu artık iptal edilemez.')
        return redirect('appointment_detail', uuid=uuid)

    try:
        with transaction.atomic():
            old_status = appointment.status
            appointment.status = 'cancelled'
            appointment.cancelled_at = timezone.now()
            appointment.cancelled_by = request.user
            appointment.cancellation_reason = request.POST.get('cancellation_reason', 'Müşteri tarafından iptal edildi.')
            appointment.save()

            AppointmentStatusHistory.objects.create(
                appointment=appointment, 
                old_status=old_status, 
                new_status='cancelled',
                changed_by=request.user, 
                reason=appointment.cancellation_reason
            )
            
            send_notification(
                user=request.user, 
                notification_type='appointment_cancelled',
                title='Randevu İptal Edildi',
                message=f'{appointment.service.name} için {appointment.date_time.strftime("%d.%m.%Y %H:%M")} tarihli randevunuz iptal edildi.',
                appointment=appointment
            )
            
            messages.success(request, 'Randevu başarıyla iptal edildi.')
            logger.info(f'Appointment cancelled: {appointment.uuid} by {request.user.username}')
    except Exception as e:
        logger.error(f'Error cancelling appointment {appointment.uuid}: {e}')
        messages.error(request, 'Randevu iptal edilirken bir hata oluştu.')

    return redirect('appointment_list')


@login_required
def appointment_reschedule(request, uuid):
    appointment = get_object_or_404(Appointment, uuid=uuid, user=request.user)

    if not appointment.can_be_rescheduled():
        messages.error(request, 'Bu randevu yeniden planlanamaz.')
        return redirect('appointment_detail', uuid=uuid)

    if request.method == 'POST':
        form = AppointmentRescheduleForm(request.POST, appointment=appointment)
        if form.is_valid():
            try:
                with transaction.atomic():
                    old_datetime_str = appointment.date_time.strftime("%d.%m.%Y %H:%M")
                    new_datetime = form.cleaned_data['new_date_time']
                    reason = form.cleaned_data.get('reason', 'Müşteri tarafından yeniden planlandı.')

                    appointment.date_time = new_datetime
                    appointment.end_time = new_datetime + timedelta(minutes=appointment.service.duration)
                    appointment.status = 'pending'
                    appointment.save()

                    AppointmentStatusHistory.objects.create(
                        appointment=appointment, 
                        old_status='confirmed', 
                        new_status='pending',
                        changed_by=request.user,
                        reason=f'Yeniden planlandı: {old_datetime_str} -> {new_datetime.strftime("%d.%m.%Y %H:%M")}. Sebep: {reason}'
                    )
                    
                    send_notification(
                        user=request.user, 
                        notification_type='appointment_created',
                        title='Randevu Yeniden Planlandı',
                        message=f'{appointment.service.name} için randevunuz {new_datetime.strftime("%d.%m.%Y %H:%M")} tarihine yeniden planlandı ve onay bekliyor.',
                        appointment=appointment,
                        action_url=reverse('appointment_detail', kwargs={'uuid': appointment.uuid})
                    )
                    
                    messages.success(request, 'Randevu başarıyla yeniden planlandı ve onay bekliyor.')
                    logger.info(f'Appointment rescheduled: {appointment.uuid} by {request.user.username}')
                    return redirect('appointment_detail', uuid=uuid)
            except Exception as e:
                logger.error(f'Error rescheduling appointment {appointment.uuid}: {e}')
                messages.error(request, 'Randevu yeniden planlanırken bir hata oluştu.')
        else:
            logger.warning(f"Appointment reschedule form invalid for {appointment.uuid}: {form.errors.as_json()}")
    else:
        form = AppointmentRescheduleForm(appointment=appointment)

    context = {'form': form, 'appointment': appointment}
    return render(request, 'appointments/appointment_reschedule.html', context)


# --- Review Views ---
@login_required
def appointment_review(request, uuid):
    appointment = get_object_or_404(Appointment, uuid=uuid, user=request.user, status='completed')

    if Review.objects.filter(appointment=appointment).exists():
        messages.info(request, 'Bu randevu için zaten bir değerlendirme yaptınız.')
        return redirect('appointment_detail', uuid=uuid)

    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            try:
                review = form.save(commit=False)
                review.appointment = appointment
                review.user = request.user
                review.service = appointment.service
                review.employee = appointment.employee
                review.save()

                send_notification(
                    user=request.user, 
                    notification_type='system',
                    title='Değerlendirmeniz Alındı',
                    message='Değerlendirmeniz için teşekkür ederiz! Görüşleriniz bizim için değerlidir.'
                )
                
                messages.success(request, 'Değerlendirmeniz başarıyla kaydedildi. Onaylandıktan sonra yayınlanacaktır.')
                logger.info(f'Review submitted for appointment {appointment.uuid} by {request.user.username}')
                return redirect('appointment_detail', uuid=uuid)
            except Exception as e:
                logger.error(f'Error creating review for appointment {appointment.uuid}: {e}')
                messages.error(request, 'Değerlendirme kaydedilirken bir hata oluştu.')
    else:
        form = ReviewForm()

    context = {'form': form, 'appointment': appointment}
    return render(request, 'appointments/appointment_review.html', context)


# --- Service Views ---
def service_list(request):
    categories = ServiceCategory.objects.filter(is_active=True, services__is_active=True)\
                                        .distinct().prefetch_related('services').order_by('order')
    context = {'categories': categories}
    return render(request, 'appointments/service_list.html', context)


def service_detail(request, slug):
    service = get_object_or_404(Service.objects.select_related('category'), slug=slug, is_active=True)
    employees = service.employees.filter(is_active=True)
    reviews = service.reviews.filter(is_approved=True).select_related('user').order_by('-created_at')[:5]
    avg_rating_data = reviews.aggregate(avg_rating=Avg('service_rating'))
    avg_rating = avg_rating_data['avg_rating'] or 0

    context = {
        'service': service,
        'employees': employees,
        'reviews': reviews,
        'avg_rating': avg_rating,
        'review_count': reviews.count()
    }
    return render(request, 'appointments/service_detail.html', context)


# --- Employee Views ---
def employee_list(request):
    employees = Employee.objects.filter(is_active=True).prefetch_related('services').order_by('name')
    context = {'employees': employees}
    return render(request, 'appointments/employee_list.html', context)


def employee_detail(request, pk):
    employee = get_object_or_404(
        Employee.objects.prefetch_related('services', 'reviews__user', 'reviews__service'), 
        pk=pk, 
        is_active=True
    )
    reviews = employee.reviews.filter(is_approved=True).order_by('-created_at')[:10]
    avg_rating = employee.average_rating
    services_offered = employee.services.filter(is_active=True)

    context = {
        'employee': employee,
        'reviews': reviews,
        'avg_rating': avg_rating,
        'services_offered': services_offered,
        'review_count': reviews.count()
    }
    return render(request, 'appointments/employee_detail.html', context)


# --- Profile Views ---
@login_required
def profile_view(request):
    try:
        profile = request.user.profile
    except CustomerProfile.DoesNotExist:
        profile = CustomerProfile.objects.create(user=request.user)

    appointments = Appointment.objects.filter(user=request.user)
    favorite_service_data = appointments.filter(status='completed')\
                                .values('service__name')\
                                .annotate(count=Count('service'))\
                                .order_by('-count').first()
    
    stats = {
        'total_appointments': appointments.count(),
        'completed_appointments': appointments.filter(status='completed').count(),
        'total_spent': appointments.filter(status='completed').aggregate(Sum('final_price'))['final_price__sum'] or 0,
        'favorite_service': favorite_service_data['service__name'] if favorite_service_data else "Yok",
    }
    
    context = {'profile': profile, 'stats': stats}
    return render(request, 'appointments/profile.html', context)


@login_required
def profile_edit(request):
    try:
        profile = request.user.profile
    except CustomerProfile.DoesNotExist:
        profile = CustomerProfile.objects.create(user=request.user)

    if request.method == 'POST':
        form = CustomerProfileForm(request.POST, request.FILES, instance=profile)
        
        # User model fields
        request.user.first_name = request.POST.get('first_name', request.user.first_name)
        request.user.last_name = request.POST.get('last_name', request.user.last_name)
        request.user.email = request.POST.get('email', request.user.email)
        request.user.save()

        if form.is_valid():
            form.save()
            messages.success(request, 'Profiliniz başarıyla güncellendi.')
            return redirect('profile_view')
        else:
            logger.warning(f"Profile edit form invalid for {request.user.username}: {form.errors.as_json()}")
            messages.error(request, 'Lütfen formdaki hataları düzeltin.')
    else:
        form = CustomerProfileForm(instance=profile)

    context = {'form': form, 'profile': profile}
    return render(request, 'appointments/profile_edit.html', context)


# --- Notification Views ---
@login_required
def notification_list(request):
    notifications_query = Notification.objects.filter(user=request.user).order_by('-created_at')
    unread_count = notifications_query.filter(is_read=False).count()

    if request.GET.get('mark_all_read') == 'true':
        notifications_query.filter(is_read=False).update(is_read=True)
        messages.success(request, 'Tüm bildirimler okundu olarak işaretlendi.')
        return redirect('notification_list')

    paginator = Paginator(notifications_query, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {'page_obj': page_obj, 'unread_count': unread_count, 'notifications': page_obj}
    return render(request, 'appointments/notification_list.html', context)


@login_required
@require_POST
def notification_mark_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=['is_read'])

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True, 
            'unread_count': Notification.objects.filter(user=request.user, is_read=False).count()
        })

    if notification.action_url:
        return redirect(notification.action_url)
    return redirect(request.META.get('HTTP_REFERER', 'notification_list'))


# --- API Views ---
def api_services(request):
    """Hizmetleri döndüren API endpoint"""
    category_id = request.GET.get('category_id')
    services_query = Service.objects.filter(is_active=True).select_related('category')
    
    if category_id:
        services_query = services_query.filter(category_id=category_id)

    data = []
    for service in services_query:
        data.append({
            'id': service.id,
            'name': service.name,
            'description': service.description,
            'duration': service.duration,
            'price': float(service.price),
            'category_id': service.category.id,
            'category_name': service.category.name,
            'icon': service.category.icon if hasattr(service.category, 'icon') else 'fas fa-star'
        })
    
    return JsonResponse(data, safe=False)


def api_employees(request):
    """Çalışanları döndüren API endpoint"""
    service_id = request.GET.get('service_id')
    employees_query = Employee.objects.filter(is_active=True)
    
    if service_id:
        employees_query = employees_query.filter(services__id=service_id).distinct()

    data = []
    for employee in employees_query:
        data.append({
            'id': employee.id,
            'name': employee.name,
            'title': employee.title,
            'specialty': employee.specialty,
            'average_rating': float(employee.average_rating) if employee.average_rating else 0,
            'icon': 'fas fa-user-tie'
        })
    
    return JsonResponse(data, safe=False)


def api_available_times(request):
    """Müsait saatleri döndüren API endpoint"""
    employee_id = request.GET.get('employee_id')
    date_str = request.GET.get('date')
    service_id = request.GET.get('service_id')

    # Parametreleri kontrol et
    if not all([employee_id, date_str, service_id]):
        return JsonResponse({
            'error': 'Eksik parametreler: employee_id, date, service_id gerekli.',
            'time_slots': []
        }, status=400)

    try:
        employee = Employee.objects.get(id=employee_id, is_active=True)
        service = Service.objects.get(id=service_id, is_active=True)
        appointment_date = datetime.strptime(date_str, '%Y-%m-%d').date()

        # Geçmiş tarih kontrolü
        if appointment_date < timezone.now().date():
            return JsonResponse({
                'error': 'Geçmiş tarih için saat sorgulanamaz.',
                'time_slots': []
            })

        # Çok ileri tarih kontrolü (90 gün)
        max_date = timezone.now().date() + timedelta(days=90)
        if appointment_date > max_date:
            return JsonResponse({
                'error': 'En fazla 90 gün sonrası için randevu alabilirsiniz.',
                'time_slots': []
            })

        # Pazar günü kontrolü
        if appointment_date.weekday() == 6:  # 6 = Pazar
            return JsonResponse({
                'error': 'Pazar günleri kapalıyız.',
                'time_slots': []
            })

        # generate_time_slots fonksiyonunu kullan
        try:
            time_slots = generate_time_slots(employee, appointment_date, service)
        except Exception as slot_error:
            logger.error(f"Time slot generation error: {str(slot_error)}")
            time_slots = []
        
        return JsonResponse({
            'time_slots': time_slots,
            'message': f'{len(time_slots)} müsait saat bulundu.' if time_slots else 'Bu tarihte müsait saat bulunmamaktadır.'
        })
        
    except Employee.DoesNotExist:
        return JsonResponse({'error': 'Geçersiz uzman ID.', 'time_slots': []}, status=404)
    except Service.DoesNotExist:
        return JsonResponse({'error': 'Geçersiz hizmet ID.', 'time_slots': []}, status=404)
    except ValueError as e:
        logger.error(f"Date parsing error: {str(e)}")
        return JsonResponse({'error': 'Geçersiz tarih formatı. YYYY-MM-DD kullanın.', 'time_slots': []}, status=400)
    except Exception as e:
        logger.error(f"API available_times error: {str(e)}")
        return JsonResponse({'error': f'Sunucu hatası: {str(e)}', 'time_slots': []}, status=500)


@login_required
def api_appointments_calendar(request):
    start_str = request.GET.get('start')
    end_str = request.GET.get('end')

    # Gelen tarihleri parse et
    try:
        start_date = timezone.make_aware(datetime.fromisoformat(start_str.split('T')[0])) if start_str else timezone.now() - timedelta(days=30)
        end_date = timezone.make_aware(datetime.fromisoformat(end_str.split('T')[0])) if end_str else timezone.now() + timedelta(days=30)
    except:
        start_date = timezone.now() - timedelta(days=30)
        end_date = timezone.now() + timedelta(days=30)

    appointments = Appointment.objects.filter(
        user=request.user,
        status__in=['pending', 'confirmed', 'completed'],
        date_time__gte=start_date,
        date_time__lte=end_date
    ).select_related('service', 'employee')

    color_map = {
        'pending': '#ffc107', 
        'confirmed': '#28a745', 
        'completed': '#6c757d',
        'cancelled': '#dc3545', 
        'no_show': '#fd7e14', 
        'in_progress': '#17a2b8'
    }
    
    events = []
    for apt in appointments:
        events.append({
            'id': str(apt.uuid),
            'title': f"{apt.service.name} ({apt.employee.name})",
            'start': apt.date_time.isoformat(),
            'end': apt.end_time.isoformat() if apt.end_time else (apt.date_time + timedelta(minutes=apt.service.duration)).isoformat(),
            'backgroundColor': color_map.get(apt.status, '#6c757d'),
            'borderColor': color_map.get(apt.status, '#6c757d'),
            'url': reverse('appointment_detail', kwargs={'uuid': apt.uuid}),
            'extendedProps': {
                'status': apt.get_status_display(), 
                'service': apt.service.name, 
                'employee': apt.employee.name
            }
        })
    
    return JsonResponse(events, safe=False)


@login_required
def api_notifications_count(request):
    count = Notification.objects.filter(user=request.user, is_read=False).count()
    return JsonResponse({'unread_count': min(count, 99)})


# --- Utility Views ---
def about_view(request):
    stats = {
        'total_customers': User.objects.filter(is_active=True).count(),
        'total_appointments': Appointment.objects.count(),
        'total_services': Service.objects.filter(is_active=True).count(),
        'average_rating': Review.objects.filter(is_approved=True).aggregate(Avg('rating'))['rating__avg'] or 0,
    }
    featured_employees = Employee.objects.filter(is_active=True).order_by('?')[:4]
    context = {'stats': stats, 'featured_employees': featured_employees}
    return render(request, 'appointments/about.html', context)


def faq_view(request):
    faqs_by_category = {}
    all_faqs = FAQ.objects.filter(is_active=True).order_by('category', 'order')
    
    for faq in all_faqs:
        category_name = faq.category if faq.category else "Genel Sorular"
        if category_name not in faqs_by_category:
            faqs_by_category[category_name] = []
        faqs_by_category[category_name].append(faq)
    
    context = {'faqs_by_category': faqs_by_category}
    return render(request, 'appointments/faq.html', context)


def contact_view(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            contact_message = form.save()
            
            # Admin'e e-posta gönder
            try:
                send_mail(
                    subject=f"Yeni İletişim Formu Mesajı: {contact_message.subject}",
                    message=f"Gönderen: {contact_message.name} ({contact_message.email})\nTelefon: {contact_message.phone}\n\nMesaj:\n{contact_message.message}",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[settings.CONTACT_EMAIL],
                    fail_silently=False
                )
            except Exception as e:
                logger.error(f"Failed to send contact form email to admin: {e}")

            messages.success(request, 'Mesajınız başarıyla gönderildi. En kısa sürede size dönüş yapacağız.')
            return redirect('contact')
        else:
            logger.warning(f"Contact form invalid: {form.errors.as_json()}")
            messages.error(request, 'Lütfen formdaki hataları düzeltin.')
    else:
        form = ContactForm()
    
    context = {'form': form}
    return render(request, 'appointments/contact.html', context)


# --- Error Views ---
def handler404(request, exception):
    return render(request, 'errors/404.html', {}, status=404)


def handler500(request):
    return render(request, 'errors/500.html', {}, status=500)


# --- Staff Views ---
@staff_required
def staff_dashboard(request):
    today = timezone.now().date()
    today_appointments = Appointment.objects.filter(date_time__date=today).select_related('user', 'service', 'employee')
    
    stats = {
        'today_total': today_appointments.count(),
        'today_pending': today_appointments.filter(status='pending').count(),
        'today_confirmed': today_appointments.filter(status='confirmed').count(),
        'today_completed': today_appointments.filter(status='completed').count(),
        'overall_pending': Appointment.objects.filter(status='pending').count()
    }
    
    recent_appointments = Appointment.objects.select_related('user', 'service', 'employee').order_by('-created_at')[:10]
    pending_appointments = Appointment.objects.filter(status='pending').select_related('user', 'service', 'employee').order_by('date_time')[:10]

    context = {
        'stats': stats,
        'today_appointments': today_appointments,
        'recent_appointments': recent_appointments,
        'pending_appointments': pending_appointments,
    }
    return render(request, 'staff/dashboard.html', context)


@staff_required
@require_POST
def staff_manage_appointment(request, uuid):
    appointment = get_object_or_404(Appointment, uuid=uuid)
    action = request.POST.get('action')

    if action == 'confirm' and appointment.status == 'pending':
        appointment.status = 'confirmed'
        reason = "Personel tarafından onaylandı."
        send_notification(
            user=appointment.user, 
            notification_type='appointment_confirmed',
            title='Randevunuz Onaylandı',
            message=f'{appointment.service.name} için {appointment.date_time.strftime("%d.%m.%Y %H:%M")} tarihli randevunuz onaylandı.',
            appointment=appointment,
            action_url=reverse('appointment_detail', kwargs={'uuid': appointment.uuid})
        )
        messages.success(request, f"Randevu #{appointment.id} onaylandı.")
    elif action == 'reject' and appointment.status == 'pending':
        appointment.status = 'cancelled'
        reason = request.POST.get('rejection_reason', "Personel tarafından reddedildi/iptal edildi.")
        appointment.cancellation_reason = reason
        appointment.cancelled_by = request.user
        appointment.cancelled_at = timezone.now()
        send_notification(
            user=appointment.user, 
            notification_type='appointment_cancelled',
            title='Randevunuz Reddedildi',
            message=f'{appointment.service.name} için {appointment.date_time.strftime("%d.%m.%Y %H:%M")} tarihli randevunuz reddedildi. Sebep: {reason}',
            appointment=appointment
        )
        messages.warning(request, f"Randevu #{appointment.id} reddedildi.")
    elif action == 'complete' and appointment.status == 'confirmed':
        appointment.status = 'completed'
        reason = "Randevu tamamlandı."
        messages.success(request, f"Randevu #{appointment.id} tamamlandı olarak işaretlendi.")
    else:
        messages.error(request, "Geçersiz işlem veya randevu durumu.")
        return redirect('staff_dashboard')

    appointment.save()
    
    AppointmentStatusHistory.objects.create(
        appointment=appointment, 
        old_status=appointment.status if action != 'confirm' else 'pending', 
        new_status=appointment.status,
        changed_by=request.user, 
        reason=reason
    )
    
    logger.info(f"Appointment {appointment.uuid} status changed to {appointment.status} by staff {request.user.username}")
    return redirect('staff_dashboard')