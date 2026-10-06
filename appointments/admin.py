# appointments/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import (
    Service, ServiceCategory, Employee, Appointment, Notification,
    Review, CustomerProfile, BusinessHours, Holiday, FAQ,
    ContactMessage, AppointmentStatusHistory
)

# Inline admin for status history
class AppointmentStatusHistoryInline(admin.TabularInline):
    model = AppointmentStatusHistory
    extra = 0
    readonly_fields = ('created_at', 'old_status', 'new_status', 'changed_by', 'reason')
    can_delete = False

@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'icon', 'color_display', 'order', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)
    ordering = ('order', 'name')
    
    def color_display(self, obj):
        return format_html(
            '<span style="background-color: {}; padding: 3px 10px; border-radius: 3px; color: white;">{}</span>',
            obj.color, obj.color
        )
    color_display.short_description = 'Renk'

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'duration', 'price_display', 'is_active')
    list_filter = ('category', 'is_active')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    
    def price_display(self, obj):
        return f'₺{obj.price}'
    price_display.short_description = 'Fiyat'

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('name', 'title', 'specialty', 'phone', 'is_active', 'average_rating_display')
    list_filter = ('is_active', 'services')
    search_fields = ('name', 'specialty', 'email')
    filter_horizontal = ('services',)
    
    fieldsets = (
        ('Temel Bilgiler', {
            'fields': ('user', 'name', 'title', 'specialty', 'bio', 'photo')
        }),
        ('İletişim', {
            'fields': ('phone', 'email')
        }),
        ('Hizmetler', {
            'fields': ('services', 'is_active')
        }),
        ('Çalışma Saatleri', {
            'fields': (
                ('monday_start', 'monday_end'),
                ('tuesday_start', 'tuesday_end'),
                ('wednesday_start', 'wednesday_end'),
                ('thursday_start', 'thursday_end'),
                ('friday_start', 'friday_end'),
                ('saturday_start', 'saturday_end'),
                ('sunday_start', 'sunday_end'),
            )
        }),
    )
    
    def average_rating_display(self, obj):
        rating = obj.average_rating
        if rating:
            return f'⭐ {rating:.1f}'
        return '-'
    average_rating_display.short_description = 'Ortalama Puan'

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_link', 'service', 'employee', 'date_time_display', 
                    'status_badge', 'payment_status_badge', 'action_buttons')
    list_filter = ('status', 'payment_status', 'date_time', 'service', 'employee')
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name', 
                     'service__name', 'employee__name', 'uuid')
    date_hierarchy = 'date_time'
    readonly_fields = ('uuid', 'created_at', 'updated_at', 'end_time', 'final_price')
    inlines = [AppointmentStatusHistoryInline]
    
    fieldsets = (
        ('Randevu Bilgileri', {
            'fields': ('uuid', 'user', 'service', 'employee', 'date_time', 'end_time')
        }),
        ('Durum', {
            'fields': ('status', 'payment_status', 'price', 'discount', 'final_price')
        }),
        ('Notlar', {
            'fields': ('notes', 'internal_notes')
        }),
        ('İptal Bilgileri', {
            'fields': ('cancelled_at', 'cancelled_by', 'cancellation_reason'),
            'classes': ('collapse',)
        }),
        ('Hatırlatmalar', {
            'fields': ('reminder_sent_24h', 'reminder_sent_2h'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['confirm_appointments', 'cancel_appointments', 'complete_appointments']
    
    def user_link(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.get_full_name() or obj.user.username)
    user_link.short_description = 'Müşteri'
    
    def date_time_display(self, obj):
        return obj.date_time.strftime('%d.%m.%Y %H:%M')
    date_time_display.short_description = 'Tarih/Saat'
    
    def status_badge(self, obj):
        colors = {
            'pending': 'orange',
            'confirmed': 'green',
            'completed': 'blue',
            'cancelled': 'red',
            'no_show': 'gray'
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            colors.get(obj.status, 'gray'), obj.get_status_display()
        )
    status_badge.short_description = 'Durum'
    
    def payment_status_badge(self, obj):
        colors = {
            'pending': 'orange',
            'paid': 'green',
            'refunded': 'red'
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            colors.get(obj.payment_status, 'gray'), obj.get_payment_status_display()
        )
    payment_status_badge.short_description = 'Ödeme'
    
    def action_buttons(self, obj):
        buttons = []
        
        if obj.status == 'pending':
            buttons.append(
                format_html(
                    '<a class="button" href="{}" style="background-color: green; color: white; padding: 5px 10px; text-decoration: none; border-radius: 3px;">Onayla</a>',
                    reverse('admin:appointment_confirm', args=[obj.pk])
                )
            )
        
        if obj.status in ['pending', 'confirmed']:
            buttons.append(
                format_html(
                    '<a class="button" href="{}" style="background-color: red; color: white; padding: 5px 10px; text-decoration: none; border-radius: 3px; margin-left: 5px;">İptal</a>',
                    reverse('admin:appointment_cancel', args=[obj.pk])
                )
            )
        
        return format_html(' '.join(buttons))
    action_buttons.short_description = 'İşlemler'
    
    def confirm_appointments(self, request, queryset):
        count = 0
        for appointment in queryset.filter(status='pending'):
            appointment.status = 'confirmed'
            appointment.save()
            
            # Status history
            AppointmentStatusHistory.objects.create(
                appointment=appointment,
                old_status='pending',
                new_status='confirmed',
                changed_by=request.user,
                reason='Admin tarafından onaylandı'
            )
            
            # Send notification
            from .utils import send_notification
            send_notification(
                user=appointment.user,
                notification_type='appointment_confirmed',
                title='Randevunuz Onaylandı',
                message=f'{appointment.service.name} için {appointment.date_time.strftime("%d.%m.%Y %H:%M")} tarihli randevunuz onaylandı.',
                appointment=appointment
            )
            count += 1
        
        self.message_user(request, f'{count} randevu onaylandı.')
    confirm_appointments.short_description = 'Seçili randevuları onayla'
    
    def cancel_appointments(self, request, queryset):
        count = 0
        for appointment in queryset.exclude(status='cancelled'):
            old_status = appointment.status
            appointment.status = 'cancelled'
            appointment.cancelled_at = timezone.now()
            appointment.cancelled_by = request.user
            appointment.cancellation_reason = 'Admin tarafından iptal edildi'
            appointment.save()
            
            # Status history
            AppointmentStatusHistory.objects.create(
                appointment=appointment,
                old_status=old_status,
                new_status='cancelled',
                changed_by=request.user,
                reason='Admin tarafından iptal edildi'
            )
            count += 1
        
        self.message_user(request, f'{count} randevu iptal edildi.')
    cancel_appointments.short_description = 'Seçili randevuları iptal et'
    
    def complete_appointments(self, request, queryset):
        count = 0
        for appointment in queryset.filter(status='confirmed'):
            appointment.status = 'completed'
            appointment.payment_status = 'paid'
            appointment.save()
            
            # Status history
            AppointmentStatusHistory.objects.create(
                appointment=appointment,
                old_status='confirmed',
                new_status='completed',
                changed_by=request.user,
                reason='Admin tarafından tamamlandı olarak işaretlendi'
            )
            count += 1
        
        self.message_user(request, f'{count} randevu tamamlandı olarak işaretlendi.')
    complete_appointments.short_description = 'Seçili randevuları tamamlanmış olarak işaretle'
    
    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('<int:appointment_id>/confirm/', self.admin_site.admin_view(self.confirm_view), name='appointment_confirm'),
            path('<int:appointment_id>/cancel/', self.admin_site.admin_view(self.cancel_view), name='appointment_cancel'),
        ]
        return custom_urls + urls
    
    def confirm_view(self, request, appointment_id):
        from django.shortcuts import redirect
        from django.contrib import messages
        
        appointment = self.get_object(request, appointment_id)
        if appointment and appointment.status == 'pending':
            appointment.status = 'confirmed'
            appointment.save()
            
            # Status history
            AppointmentStatusHistory.objects.create(
                appointment=appointment,
                old_status='pending',
                new_status='confirmed',
                changed_by=request.user,
                reason='Admin panelinden onaylandı'
            )
            
            messages.success(request, f'Randevu #{appointment.id} onaylandı.')
        
        return redirect('admin:appointments_appointment_changelist')
    
    def cancel_view(self, request, appointment_id):
        from django.shortcuts import redirect
        from django.contrib import messages
        
        appointment = self.get_object(request, appointment_id)
        if appointment and appointment.status in ['pending', 'confirmed']:
            old_status = appointment.status
            appointment.status = 'cancelled'
            appointment.cancelled_at = timezone.now()
            appointment.cancelled_by = request.user
            appointment.save()
            
            # Status history
            AppointmentStatusHistory.objects.create(
                appointment=appointment,
                old_status=old_status,
                new_status='cancelled',
                changed_by=request.user,
                reason='Admin panelinden iptal edildi'
            )
            
            messages.success(request, f'Randevu #{appointment.id} iptal edildi.')
        
        return redirect('admin:appointments_appointment_changelist')

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('user', 'service', 'employee', 'rating', 'is_approved', 'is_featured', 'created_at')
    list_filter = ('is_approved', 'is_featured', 'rating', 'created_at')
    search_fields = ('user__username', 'title', 'comment')
    actions = ['approve_reviews', 'feature_reviews']
    
    def approve_reviews(self, request, queryset):
        count = queryset.update(is_approved=True)
        self.message_user(request, f'{count} değerlendirme onaylandı.')
    approve_reviews.short_description = 'Seçili değerlendirmeleri onayla'
    
    def feature_reviews(self, request, queryset):
        count = queryset.update(is_featured=True, is_approved=True)
        self.message_user(request, f'{count} değerlendirme öne çıkarıldı.')
    feature_reviews.short_description = 'Seçili değerlendirmeleri öne çıkar'

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'type', 'title', 'is_read', 'created_at')
    list_filter = ('type', 'is_read', 'created_at')
    search_fields = ('user__username', 'title', 'message')
    date_hierarchy = 'created_at'

@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'gender', 'accepts_marketing', 'accepts_sms', 'total_appointments')
    list_filter = ('gender', 'accepts_marketing', 'accepts_sms')
    search_fields = ('user__username', 'user__email', 'phone')

@admin.register(BusinessHours)
class BusinessHoursAdmin(admin.ModelAdmin):
    list_display = ('get_day_display', 'is_open', 'open_time', 'close_time', 'break_start', 'break_end')
    list_editable = ('is_open', 'open_time', 'close_time', 'break_start', 'break_end')
    ordering = ('day_of_week',)
    
    def get_day_display(self, obj):
        days = ['Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi', 'Pazar']
        return days[obj.day_of_week]
    get_day_display.short_description = 'Gün'

@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ('question', 'category', 'order', 'is_active')
    list_filter = ('category', 'is_active')
    search_fields = ('question', 'answer')
    list_editable = ('order', 'is_active')

@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'subject', 'is_replied', 'created_at')
    list_filter = ('is_replied', 'created_at')
    search_fields = ('name', 'email', 'subject', 'message')
    readonly_fields = ('created_at',)
    
    actions = ['mark_as_replied']
    
    def mark_as_replied(self, request, queryset):
        count = queryset.update(is_replied=True, replied_at=timezone.now(), replied_by=request.user)
        self.message_user(request, f'{count} mesaj yanıtlandı olarak işaretlendi.')
    mark_as_replied.short_description = 'Seçili mesajları yanıtlandı olarak işaretle'

# Site header ve title özelleştirme
admin.site.site_header = "BeautyTime Yönetim Paneli"
admin.site.site_title = "BeautyTime Admin"
admin.site.index_title = "Hoş Geldiniz"