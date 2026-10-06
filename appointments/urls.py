# appointments/urls.py
from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import views

# Main URL patterns
urlpatterns = [
    # Home and main pages
    path('', views.home, name='home'),
    path('about/', views.about_view, name='about'),
    path('contact/', views.contact_view, name='contact'),
    path('faq/', views.faq_view, name='faq'),
    
    # Authentication URLs
    path('accounts/login/', views.CustomLoginView.as_view(), name='login'),
    path('accounts/logout/', views.CustomLogoutView.as_view(), name='logout'),
    path('accounts/register/', views.SignUpView.as_view(), name='register'),
    
    # Password reset URLs
    path('accounts/password_reset/', 
         auth_views.PasswordResetView.as_view(
             template_name='registration/password_reset_form.html',
             email_template_name='registration/password_reset_email.html',
             success_url='/accounts/password_reset/done/'
         ), 
         name='password_reset'),
    path('accounts/password_reset/done/', 
         auth_views.PasswordResetDoneView.as_view(
             template_name='registration/password_reset_done.html'
         ), 
         name='password_reset_done'),
    path('accounts/reset/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(
             template_name='registration/password_reset_confirm.html',
             success_url='/accounts/reset/done/'
         ), 
         name='password_reset_confirm'),
    path('accounts/reset/done/', 
         auth_views.PasswordResetCompleteView.as_view(
             template_name='registration/password_reset_complete.html'
         ), 
         name='password_reset_complete'),
    
    # Password change URLs
    path('accounts/password_change/', 
         auth_views.PasswordChangeView.as_view(
             template_name='registration/password_change_form.html',
             success_url='/accounts/password_change/done/'
         ), 
         name='password_change'),
    path('accounts/password_change/done/', 
         auth_views.PasswordChangeDoneView.as_view(
             template_name='registration/password_change_done.html'
         ), 
         name='password_change_done'),
    
    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Appointment URLs
    path('appointments/', views.appointment_list, name='appointment_list'),
    path('appointments/create/', views.appointment_create, name='appointment_create'),
    path('appointments/<uuid:uuid>/', views.appointment_detail, name='appointment_detail'),
    path('appointments/<uuid:uuid>/cancel/', views.appointment_cancel, name='appointment_cancel'),
    path('appointments/<uuid:uuid>/reschedule/', views.appointment_reschedule, name='appointment_reschedule'),
    path('appointments/<uuid:uuid>/review/', views.appointment_review, name='appointment_review'),
    
    # Service URLs
    path('services/', views.service_list, name='service_list'),
    path('services/<slug:slug>/', views.service_detail, name='service_detail'),
    
    # Employee URLs
    path('employees/', views.employee_list, name='employee_list'),
    path('employees/<int:pk>/', views.employee_detail, name='employee_detail'),
    
    # Profile URLs
    path('profile/', views.profile_view, name='profile_view'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    
    # Notification URLs
    path('notifications/', views.notification_list, name='notification_list'),
    path('notifications/<int:pk>/read/', views.notification_mark_read, name='notification_mark_read'),
    
    # API URLs
    path('api/', include([
        path('services/', views.api_services, name='api_services'),
        path('employees/', views.api_employees, name='api_employees'),
        path('available-times/', views.api_available_times, name='api_available_times'),
        path('appointments/calendar/', views.api_appointments_calendar, name='api_appointments_calendar'),
        path('notifications/count/', views.api_notifications_count, name='api_notifications_count'),
    ])),
]

# Staff URLs (Admin functionality)
staff_patterns = [
    path('staff/', include([
        path('', views.staff_dashboard, name='staff_dashboard'),
        path('appointments/<uuid:uuid>/manage/', views.staff_manage_appointment, name='staff_manage_appointment'),
    ])),
]

urlpatterns += staff_patterns