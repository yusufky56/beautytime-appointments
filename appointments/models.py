# appointments/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.urls import reverse
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta
import uuid

class TimeStampedModel(models.Model):
    """Base model with created_at and updated_at fields"""
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Oluşturulma Tarihi")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Güncellenme Tarihi")

    class Meta:
        abstract = True

class ServiceCategory(TimeStampedModel):
    """Service categories for better organization"""
    name = models.CharField(max_length=100, verbose_name="Kategori Adı")
    description = models.TextField(blank=True, verbose_name="Açıklama")
    icon = models.CharField(max_length=50, default='fas fa-star', verbose_name="İkon")
    color = models.CharField(max_length=7, default='#667eea', verbose_name="Renk")
    is_active = models.BooleanField(default=True, verbose_name="Aktif")
    order = models.PositiveIntegerField(default=0, verbose_name="Sıralama")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Hizmet Kategorisi"
        verbose_name_plural = "Hizmet Kategorileri"
        ordering = ['order', 'name']

class Service(TimeStampedModel):
    """Enhanced Service model"""
    id = models.AutoField(primary_key=True)
    category = models.ForeignKey(ServiceCategory, on_delete=models.CASCADE, related_name='services', verbose_name="Kategori")
    name = models.CharField(max_length=255, verbose_name="Hizmet Adı")
    description = models.TextField(blank=True, verbose_name="Açıklama")
    duration = models.PositiveIntegerField(verbose_name="Süre (dakika)", validators=[MinValueValidator(15), MaxValueValidator(480)])
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Fiyat")
    image = models.ImageField(upload_to='services/', blank=True, null=True, verbose_name="Resim")
    is_active = models.BooleanField(default=True, verbose_name="Aktif")
    requires_consultation = models.BooleanField(default=False, verbose_name="Konsültasyon Gerekli")
    max_advance_booking_days = models.PositiveIntegerField(default=90, verbose_name="Maksimum Önceden Rezervasyon (Gün)")
    
    # SEO fields
    slug = models.SlugField(unique=True, blank=True, verbose_name="URL")
    meta_description = models.CharField(max_length=160, blank=True, verbose_name="Meta Açıklama")

    def __str__(self):
        return f"{self.name} - ₺{self.price}"

    def get_absolute_url(self):
        return reverse('service_detail', kwargs={'slug': self.slug})

    class Meta:
        verbose_name = "Hizmet"
        verbose_name_plural = "Hizmetler"
        ordering = ['category', 'name']

class Employee(TimeStampedModel):
    """Enhanced Employee model"""
    id = models.AutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Kullanıcı")
    name = models.CharField(max_length=255, verbose_name="Ad Soyad")
    title = models.CharField(max_length=100, blank=True, verbose_name="Ünvan")
    specialty = models.CharField(max_length=255, verbose_name="Uzmanlık Alanı")
    bio = models.TextField(blank=True, verbose_name="Biyografi")
    photo = models.ImageField(upload_to='employees/', blank=True, null=True, verbose_name="Fotoğraf")
    phone = models.CharField(max_length=20, blank=True, verbose_name="Telefon")
    email = models.EmailField(blank=True, verbose_name="E-posta")
    is_active = models.BooleanField(default=True, verbose_name="Aktif")
    hire_date = models.DateField(null=True, blank=True, verbose_name="İşe Başlama Tarihi")
    
    # Services this employee can provide
    services = models.ManyToManyField(Service, related_name='employees', verbose_name="Sunduğu Hizmetler")
    
    # Working schedule
    monday_start = models.TimeField(null=True, blank=True, verbose_name="Pazartesi Başlangıç")
    monday_end = models.TimeField(null=True, blank=True, verbose_name="Pazartesi Bitiş")
    tuesday_start = models.TimeField(null=True, blank=True, verbose_name="Salı Başlangıç")
    tuesday_end = models.TimeField(null=True, blank=True, verbose_name="Salı Bitiş")
    wednesday_start = models.TimeField(null=True, blank=True, verbose_name="Çarşamba Başlangıç")
    wednesday_end = models.TimeField(null=True, blank=True, verbose_name="Çarşamba Bitiş")
    thursday_start = models.TimeField(null=True, blank=True, verbose_name="Perşembe Başlangıç")
    thursday_end = models.TimeField(null=True, blank=True, verbose_name="Perşembe Bitiş")
    friday_start = models.TimeField(null=True, blank=True, verbose_name="Cuma Başlangıç")
    friday_end = models.TimeField(null=True, blank=True, verbose_name="Cuma Bitiş")
    saturday_start = models.TimeField(null=True, blank=True, verbose_name="Cumartesi Başlangıç")
    saturday_end = models.TimeField(null=True, blank=True, verbose_name="Cumartesi Bitiş")
    sunday_start = models.TimeField(null=True, blank=True, verbose_name="Pazar Başlangıç")
    sunday_end = models.TimeField(null=True, blank=True, verbose_name="Pazar Bitiş")

    def __str__(self):
        return f"{self.name} ({self.specialty})"

    def get_working_hours(self, day):
        """Get working hours for a specific day (0=Monday, 6=Sunday)"""
        days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        day_name = days[day]
        start_time = getattr(self, f"{day_name}_start")
        end_time = getattr(self, f"{day_name}_end")
        return (start_time, end_time) if start_time and end_time else (None, None)

    def is_available(self, date_time):
        """Check if employee is available at given datetime"""
        # Working hours are stored in local time, so compare in the local time zone
        if timezone.is_aware(date_time):
            date_time = timezone.localtime(date_time)
        day_of_week = date_time.weekday()
        start_time, end_time = self.get_working_hours(day_of_week)
        
        if not start_time or not end_time:
            return False
            
        time_only = date_time.time()
        return start_time <= time_only <= end_time

    @property
    def average_rating(self):
        """Calculate average rating from reviews"""
        reviews = self.reviews.filter(is_approved=True)
        if reviews.exists():
            return reviews.aggregate(models.Avg('rating'))['rating__avg']
        return 0

    class Meta:
        verbose_name = "Çalışan"
        verbose_name_plural = "Çalışanlar"
        ordering = ['name']

class Appointment(TimeStampedModel):
    """Enhanced Appointment model"""
    STATUS_CHOICES = [
        ('pending', 'Beklemede'),
        ('confirmed', 'Onaylandı'),
        ('in_progress', 'Devam Ediyor'),
        ('completed', 'Tamamlandı'),
        ('cancelled', 'İptal Edildi'),
        ('no_show', 'Gelmedi'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Beklemede'),
        ('paid', 'Ödendi'),
        ('refunded', 'İade Edildi'),
    ]

    id = models.AutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='appointments', verbose_name="Müşteri")
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='appointments', verbose_name="Hizmet")
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='appointments', verbose_name="Çalışan")
    date_time = models.DateTimeField(verbose_name="Randevu Tarihi ve Saati")
    end_time = models.DateTimeField(null=True, blank=True, verbose_name="Bitiş Saati")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Durum")
    
    # Additional fields
    notes = models.TextField(blank=True, verbose_name="Notlar")
    internal_notes = models.TextField(blank=True, verbose_name="Dahili Notlar")
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Fiyat")
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="İndirim")
    final_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Final Fiyat")
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending', verbose_name="Ödeme Durumu")
    
    # Reminders
    reminder_sent_24h = models.BooleanField(default=False, verbose_name="24 Saat Hatırlatması Gönderildi")
    reminder_sent_2h = models.BooleanField(default=False, verbose_name="2 Saat Hatırlatması Gönderildi")
    
    # Cancellation
    cancelled_at = models.DateTimeField(null=True, blank=True, verbose_name="İptal Tarihi")
    cancelled_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='cancelled_appointments', verbose_name="İptal Eden")
    cancellation_reason = models.TextField(blank=True, verbose_name="İptal Nedeni")

    def save(self, *args, **kwargs):
        # Set end time based on service duration
        if not self.end_time and self.service:
            self.end_time = self.date_time + timedelta(minutes=self.service.duration)
        
        # Set price if not set
        if not self.price and self.service:
            self.price = self.service.price
        
        # Calculate final price
        if self.price is not None:
            self.final_price = self.price - self.discount

        super().save(*args, **kwargs)

    def clean(self):
        """Validate appointment data"""
        if self.date_time:
            # Check if appointment is in the past
            if self.date_time <= timezone.now():
                raise ValidationError("Randevu geçmiş bir tarih için oluşturulamaz.")
            
            # Check if employee is available
            if self.employee and not self.employee.is_available(self.date_time):
                raise ValidationError("Çalışan bu saatte müsait değil.")
            
            # Check for conflicting appointments
            if self.employee:
                conflicts = Appointment.objects.filter(
                    employee=self.employee,
                    date_time__date=self.date_time.date(),
                    status__in=['pending', 'confirmed', 'in_progress']
                )
                
                if self.pk:
                    conflicts = conflicts.exclude(pk=self.pk)
                
                # end_time is only filled in save(), so compute it here for new appointments
                end_time = self.end_time
                if end_time is None and self.service_id:
                    end_time = self.date_time + timedelta(minutes=self.service.duration)

                for conflict in conflicts:
                    if (self.date_time < conflict.end_time and
                            end_time > conflict.date_time):
                        raise ValidationError("Bu saatte çalışanın başka bir randevusu var.")

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.service.name} ({self.date_time.strftime('%d.%m.%Y %H:%M')})"

    def get_absolute_url(self):
        return reverse('appointment_detail', kwargs={'uuid': self.uuid})

    def can_be_cancelled(self):
        """Check if appointment can be cancelled"""
        if self.status in ['cancelled', 'completed', 'no_show']:
            return False
        
        # Check if cancellation is within allowed time
        min_cancel_time = self.date_time - timedelta(hours=2)
        return timezone.now() < min_cancel_time

    def can_be_rescheduled(self):
        """Check if appointment can be rescheduled"""
        return self.status in ['pending', 'confirmed'] and self.can_be_cancelled()

    @property
    def duration_minutes(self):
        """Get appointment duration in minutes"""
        if self.end_time:
            return int((self.end_time - self.date_time).total_seconds() / 60)
        return self.service.duration if self.service else 60

    @property
    def is_today(self):
        """Check if appointment is today"""
        return self.date_time.date() == timezone.now().date()

    @property
    def is_upcoming(self):
        """Check if appointment is in the future"""
        return self.date_time > timezone.now()

    class Meta:
        verbose_name = "Randevu"
        verbose_name_plural = "Randevular"
        ordering = ['-date_time']
        indexes = [
            models.Index(fields=['date_time']),
            models.Index(fields=['status']),
            models.Index(fields=['employee', 'date_time']),
        ]

class AppointmentStatusHistory(TimeStampedModel):
    """Track appointment status changes"""
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE, related_name='status_history')
    old_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    reason = models.TextField(blank=True)

    class Meta:
        verbose_name = "Randevu Durum Geçmişi"
        verbose_name_plural = "Randevu Durum Geçmişleri"
        ordering = ['-created_at']

class Review(TimeStampedModel):
    """Customer reviews for services and employees"""
    appointment = models.OneToOneField(Appointment, on_delete=models.CASCADE, related_name='review')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='reviews')
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    
    rating = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], verbose_name="Puan")
    service_rating = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], verbose_name="Hizmet Puanı")
    employee_rating = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], verbose_name="Çalışan Puanı")
    cleanliness_rating = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], verbose_name="Temizlik Puanı")
    
    title = models.CharField(max_length=200, blank=True, verbose_name="Başlık")
    comment = models.TextField(blank=True, verbose_name="Yorum")
    pros = models.TextField(blank=True, verbose_name="Artıları")
    cons = models.TextField(blank=True, verbose_name="Eksileri")
    
    would_recommend = models.BooleanField(default=True, verbose_name="Tavsiye Eder misiniz?")
    is_approved = models.BooleanField(default=False, verbose_name="Onaylandı")
    is_featured = models.BooleanField(default=False, verbose_name="Öne Çıkarıldı")

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.service.name} ({self.rating}/5)"

    class Meta:
        verbose_name = "Değerlendirme"
        verbose_name_plural = "Değerlendirmeler"
        ordering = ['-created_at']

class Notification(TimeStampedModel):
    """Enhanced notification system"""
    NOTIFICATION_TYPES = [
        ('appointment_created', 'Randevu Oluşturuldu'),
        ('appointment_confirmed', 'Randevu Onaylandı'),
        ('appointment_cancelled', 'Randevu İptal Edildi'),
        ('appointment_reminder', 'Randevu Hatırlatması'),
        ('appointment_completed', 'Randevu Tamamlandı'),
        ('review_request', 'Değerlendirme İsteği'),
        ('promotion', 'Promosyon'),
        ('system', 'Sistem Bildirimi'),
    ]

    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES, verbose_name="Tip")
    title = models.CharField(max_length=200, verbose_name="Başlık")
    message = models.TextField(verbose_name="Mesaj")
    is_read = models.BooleanField(default=False, verbose_name="Okundu")
    is_sent_email = models.BooleanField(default=False, verbose_name="E-posta Gönderildi")
    is_sent_sms = models.BooleanField(default=False, verbose_name="SMS Gönderildi")
    
    # Related objects
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    
    # Additional data
    action_url = models.URLField(blank=True, verbose_name="Aksiyon URL")
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name="Son Geçerlilik")

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.title}"

    def mark_as_read(self):
        """Mark notification as read"""
        self.is_read = True
        self.save(update_fields=['is_read'])

    @property
    def is_expired(self):
        """Check if notification is expired"""
        return self.expires_at and self.expires_at < timezone.now()

    class Meta:
        verbose_name = "Bildirim"
        verbose_name_plural = "Bildirimler"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['type']),
        ]

class BusinessHours(TimeStampedModel):
    """Business working hours"""
    DAYS_OF_WEEK = [
        (0, 'Pazartesi'),
        (1, 'Salı'),
        (2, 'Çarşamba'),
        (3, 'Perşembe'),
        (4, 'Cuma'),
        (5, 'Cumartesi'),
        (6, 'Pazar'),
    ]

    day_of_week = models.IntegerField(choices=DAYS_OF_WEEK, unique=True)
    is_open = models.BooleanField(default=True, verbose_name="Açık")
    open_time = models.TimeField(null=True, blank=True, verbose_name="Açılış Saati")
    close_time = models.TimeField(null=True, blank=True, verbose_name="Kapanış Saati")
    break_start = models.TimeField(null=True, blank=True, verbose_name="Mola Başlangıç")
    break_end = models.TimeField(null=True, blank=True, verbose_name="Mola Bitiş")

    def __str__(self):
        day_name = dict(self.DAYS_OF_WEEK)[self.day_of_week]
        if not self.is_open:
            return f"{day_name} - Kapalı"
        return f"{day_name} - {self.open_time} - {self.close_time}"

    class Meta:
        verbose_name = "İş Saati"
        verbose_name_plural = "İş Saatleri"
        ordering = ['day_of_week']

class Holiday(TimeStampedModel):
    """Business holidays"""
    name = models.CharField(max_length=100, verbose_name="Tatil Adı")
    date = models.DateField(verbose_name="Tarih")
    is_recurring = models.BooleanField(default=False, verbose_name="Her Yıl Tekrarlanır")
    description = models.TextField(blank=True, verbose_name="Açıklama")

    def __str__(self):
        return f"{self.name} - {self.date}"

    class Meta:
        verbose_name = "Tatil"
        verbose_name_plural = "Tatiller"
        ordering = ['date']

class EmployeeBreak(TimeStampedModel):
    """Employee breaks and unavailable times"""
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='breaks')
    start_time = models.DateTimeField(verbose_name="Başlangıç")
    end_time = models.DateTimeField(verbose_name="Bitiş")
    reason = models.CharField(max_length=200, blank=True, verbose_name="Neden")
    is_recurring = models.BooleanField(default=False, verbose_name="Tekrarlanan")

    def __str__(self):
        return f"{self.employee.name} - {self.start_time} - {self.end_time}"

    class Meta:
        verbose_name = "Çalışan Molası"
        verbose_name_plural = "Çalışan Molaları"
        ordering = ['-start_time']

class CustomerProfile(TimeStampedModel):
    """Extended customer profile"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=20, blank=True, verbose_name="Telefon")
    birth_date = models.DateField(null=True, blank=True, verbose_name="Doğum Tarihi")
    gender = models.CharField(max_length=10, choices=[('M', 'Erkek'), ('F', 'Kadın'), ('O', 'Diğer')], blank=True, verbose_name="Cinsiyet")
    address = models.TextField(blank=True, verbose_name="Adres")
    
    # Preferences
    preferred_employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Tercih Edilen Çalışan")
    notification_preferences = models.JSONField(default=dict, verbose_name="Bildirim Tercihleri")
    allergies = models.TextField(blank=True, verbose_name="Alerjiler")
    skin_type = models.CharField(max_length=50, blank=True, verbose_name="Cilt Tipi")
    notes = models.TextField(blank=True, verbose_name="Notlar")
    
    # Marketing
    accepts_marketing = models.BooleanField(default=True, verbose_name="Pazarlama E-postalarını Kabul Eder")
    accepts_sms = models.BooleanField(default=True, verbose_name="SMS Kabul Eder")
    
    # Stats
    total_appointments = models.PositiveIntegerField(default=0, verbose_name="Toplam Randevu")
    total_spent = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Toplam Harcama")
    average_rating_given = models.FloatField(default=0, verbose_name="Verdiği Ortalama Puan")

    def __str__(self):
        return f"{self.user.get_full_name()} Profili"

    class Meta:
        verbose_name = "Müşteri Profili"
        verbose_name_plural = "Müşteri Profilleri"

class Promotion(TimeStampedModel):
    """Promotions and discounts"""
    DISCOUNT_TYPES = [
        ('percentage', 'Yüzde'),
        ('fixed', 'Sabit Tutar'),
        ('free_service', 'Ücretsiz Hizmet'),
    ]

    name = models.CharField(max_length=200, verbose_name="Promosyon Adı")
    description = models.TextField(verbose_name="Açıklama")
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPES, verbose_name="İndirim Tipi")
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="İndirim Değeri")
    
    # Validity
    start_date = models.DateTimeField(verbose_name="Başlangıç Tarihi")
    end_date = models.DateTimeField(verbose_name="Bitiş Tarihi")
    
    # Conditions
    min_purchase_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Minimum Alışveriş Tutarı")
    applicable_services = models.ManyToManyField(Service, blank=True, verbose_name="Geçerli Hizmetler")
    max_uses = models.PositiveIntegerField(null=True, blank=True, verbose_name="Maksimum Kullanım")
    used_count = models.PositiveIntegerField(default=0, verbose_name="Kullanım Sayısı")
    
    # Target audience
    is_for_new_customers = models.BooleanField(default=False, verbose_name="Yeni Müşteriler İçin")
    is_for_birthday = models.BooleanField(default=False, verbose_name="Doğum Günü İndirimi")
    
    is_active = models.BooleanField(default=True, verbose_name="Aktif")

    def __str__(self):
        return self.name

    @property
    def is_valid(self):
        """Check if promotion is currently valid"""
        now = timezone.now()
        return (self.is_active and 
                self.start_date <= now <= self.end_date and
                (not self.max_uses or self.used_count < self.max_uses))

    class Meta:
        verbose_name = "Promosyon"
        verbose_name_plural = "Promosyonlar"
        ordering = ['-created_at']

class FAQ(TimeStampedModel):
    """Frequently Asked Questions"""
    question = models.CharField(max_length=500, verbose_name="Soru")
    answer = models.TextField(verbose_name="Cevap")
    category = models.CharField(max_length=100, blank=True, verbose_name="Kategori")
    order = models.PositiveIntegerField(default=0, verbose_name="Sıralama")
    is_active = models.BooleanField(default=True, verbose_name="Aktif")

    def __str__(self):
        return self.question

    class Meta:
        verbose_name = "Sıkça Sorulan Soru"
        verbose_name_plural = "Sıkça Sorulan Sorular"
        ordering = ['order', 'question']

class ContactMessage(TimeStampedModel):
    """Contact form messages"""
    name = models.CharField(max_length=100, verbose_name="Ad Soyad")
    email = models.EmailField(verbose_name="E-posta")
    phone = models.CharField(max_length=20, blank=True, verbose_name="Telefon")
    subject = models.CharField(max_length=200, verbose_name="Konu")
    message = models.TextField(verbose_name="Mesaj")
    is_replied = models.BooleanField(default=False, verbose_name="Yanıtlandı")
    replied_at = models.DateTimeField(null=True, blank=True, verbose_name="Yanıtlanma Tarihi")
    replied_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Yanıtlayan")

    def __str__(self):
        return f"{self.name} - {self.subject}"

    class Meta:
        verbose_name = "İletişim Mesajı"
        verbose_name_plural = "İletişim Mesajları"
        ordering = ['-created_at']