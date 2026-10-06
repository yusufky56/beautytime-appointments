# appointments/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.forms.widgets import DateTimeInput, TimeInput, DateInput
from datetime import datetime, timedelta, time
import re

# Model imports
from .models import (
    Appointment, Service, Employee, Review, CustomerProfile,
    ContactMessage, ServiceCategory, Notification, BusinessHours,
    Holiday, Promotion, FAQ, EmployeeBreak, AppointmentStatusHistory
)

# Utils imports - is_time_slot_available fonksiyonunu ekleyelim
from .utils import is_time_slot_available, check_availability

import logging
logger = logging.getLogger(__name__)

# --- Helper Functions for Validation ---
def validate_phone_number_format(phone):
    """Validate Turkish phone number format more robustly."""
    cleaned_phone = re.sub(r'[^\d+]', '', phone)

    patterns = [
        r'^\+905\d{9}$',
        r'^905\d{9}$',
        r'^05\d{9}$',
        r'^5\d{9}$',
    ]
    for pattern in patterns:
        if re.fullmatch(pattern, cleaned_phone):
            return True
    return False


def clean_and_format_phone_number(phone):
    """Clean and format phone number to +905xxxxxxxxx."""
    cleaned_phone = re.sub(r'[^\d]', '', phone)

    if len(cleaned_phone) == 10 and cleaned_phone.startswith('5'):
        return '+90' + cleaned_phone
    elif len(cleaned_phone) == 11 and cleaned_phone.startswith('05'):
        return '+90' + cleaned_phone[1:]
    elif len(cleaned_phone) == 12 and cleaned_phone.startswith('905'):
        return '+' + cleaned_phone
    elif len(cleaned_phone) == 13 and cleaned_phone.startswith('+905'):
        return cleaned_phone
    return None


class CustomUserCreationForm(UserCreationForm):
    """Enhanced user registration form"""
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Adınız'
        }),
        label='Ad'
    )
    last_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Soyadınız'
        }),
        label='Soyad'
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'ornek@email.com'
        }),
        label='E-posta'
    )
    phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': '+90 555 123 45 67'
        }),
        label='Telefon (İsteğe Bağlı)'
    )
    birth_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control form-control-lg',
            'type': 'date'
        }),
        label='Doğum Tarihi (İsteğe Bağlı)'
    )
    gender = forms.ChoiceField(
        choices=[('', 'Belirtmek İstemiyorum'), ('M', 'Erkek'), ('F', 'Kadın'), ('O', 'Diğer')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-lg'}),
        label='Cinsiyet'
    )
    accepts_marketing = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Kampanya ve duyurular için e-posta almak istiyorum'
    )
    accepts_sms = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='SMS ile bildirim almak istiyorum'
    )
    terms_accepted = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Kullanım şartlarını ve gizlilik politikasını kabul ediyorum',
        error_messages={'required': 'Kullanım şartlarını kabul etmelisiniz.'}
    )

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Tüm alanlara Bootstrap class ekle
        for field_name, field in self.fields.items():
            if field_name not in ['accepts_marketing', 'accepts_sms', 'terms_accepted']:
                if field_name == 'gender':
                    field.widget.attrs['class'] = 'form-select form-select-lg'
                else:
                    if 'class' not in field.widget.attrs:
                        field.widget.attrs['class'] = 'form-control form-control-lg'

        # Placeholder'ları ayarla
        self.fields['username'].widget.attrs['placeholder'] = 'Kullanıcı adınızı seçin'
        self.fields['password1'].widget.attrs['placeholder'] = 'Güçlü bir şifre seçin'
        self.fields['password2'].widget.attrs['placeholder'] = 'Şifrenizi tekrar girin'

        # Label'ları Türkçeleştir
        self.fields['username'].label = 'Kullanıcı Adı'
        self.fields['password1'].label = 'Şifre'
        self.fields['password2'].label = 'Şifre Tekrar'

        # Yardım metinlerini güncelle
        self.fields['username'].help_text = 'Harfler, rakamlar ve @/./+/-/_ karakterleri kullanabilirsiniz.'
        self.fields['password1'].help_text = '''
        <ul class="small text-muted mb-0">
            <li>En az 8 karakter uzunluğunda olmalı</li>
            <li>Tamamen rakamlardan oluşamaz</li>
            <li>Çok yaygın bir şifre olamaz</li>
            <li>Kullanıcı bilgilerinize benzememelidir</li>
        </ul>
        '''
        self.fields['password2'].help_text = 'Doğrulama için yukarıdaki şifreyi tekrar girin.'

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise ValidationError("Bu e-posta adresi zaten kullanılıyor.")
        return email.lower() if email else email

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            # Telefon numarası temizleme ve doğrulama
            cleaned_phone = re.sub(r'[^\d+]', '', phone)
            
            # Farklı telefon formatlarını kontrol et
            if cleaned_phone.startswith('+905'):
                # +905XXXXXXXXX formatı (13 karakter)
                if len(cleaned_phone) != 13:
                    raise ValidationError("Telefon numarası geçersiz. Lütfen 10 haneli telefon numaranızı girin.")
            elif cleaned_phone.startswith('905'):
                # 905XXXXXXXXX formatı (12 karakter)
                if len(cleaned_phone) != 12:
                    raise ValidationError("Telefon numarası geçersiz. Lütfen 10 haneli telefon numaranızı girin.")
                cleaned_phone = '+' + cleaned_phone
            elif cleaned_phone.startswith('05'):
                # 05XXXXXXXXX formatı (11 karakter)
                if len(cleaned_phone) != 11:
                    raise ValidationError("Telefon numarası geçersiz. Lütfen 10 haneli telefon numaranızı girin.")
                cleaned_phone = '+9' + cleaned_phone
            elif cleaned_phone.startswith('5'):
                # 5XXXXXXXXX formatı (10 karakter)
                if len(cleaned_phone) != 10:
                    raise ValidationError("Telefon numarası geçersiz. Lütfen 10 haneli telefon numaranızı girin.")
                cleaned_phone = '+90' + cleaned_phone
            else:
                raise ValidationError("Lütfen geçerli bir Türkiye telefon numarası girin (5XX XXX XX XX).")
            
            return cleaned_phone
        return phone

    def clean_birth_date(self):
        birth_date = self.cleaned_data.get('birth_date')
        if birth_date:
            today = timezone.now().date()
            age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
            if age < 16:
                raise ValidationError("16 yaşından küçük kullanıcılar kayıt olamaz.")
            if age > 120:
                raise ValidationError("Geçerli bir doğum tarihi girin.")
        return birth_date

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get('terms_accepted'):
            raise ValidationError({'terms_accepted': 'Kullanım şartlarını kabul etmelisiniz.'})
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']

        if commit:
            user.save()
            # CustomerProfile oluştur
            CustomerProfile.objects.create(
                user=user,
                phone=self.cleaned_data.get('phone', ''),
                birth_date=self.cleaned_data.get('birth_date'),
                gender=self.cleaned_data.get('gender', ''),
                accepts_marketing=self.cleaned_data.get('accepts_marketing', True),
                accepts_sms=self.cleaned_data.get('accepts_sms', True)
            )
        return user


# appointments/forms.py içine eklenecek düzeltilmiş login formu

from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm as BaseAuthenticationForm

class CustomAuthenticationForm(BaseAuthenticationForm):
    """Enhanced login form with email support"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': 'form-control form-control-lg',
            'placeholder': 'Kullanıcı adı veya e-posta',
            'autofocus': True
        })
        self.fields['password'].widget.attrs.update({
            'class': 'form-control form-control-lg',
            'placeholder': 'Şifreniz'
        })
        self.fields['username'].label = 'Kullanıcı Adı / E-posta'
        self.fields['password'].label = 'Şifre'

    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if username and password:
            # Önce username ile dene
            self.user_cache = authenticate(self.request, username=username, password=password)
            
            # Eğer başarısızsa ve @ içeriyorsa email olarak dene
            if not self.user_cache and '@' in username:
                try:
                    user_obj = User.objects.get(email=username)
                    self.user_cache = authenticate(self.request, username=user_obj.username, password=password)
                except User.DoesNotExist:
                    pass
            
            if self.user_cache is None:
                raise forms.ValidationError(
                    'Kullanıcı adı/e-posta veya şifre hatalı. Lütfen kontrol edip tekrar deneyin.',
                    code='invalid_login',
                )
            else:
                self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data


class AppointmentForm(forms.ModelForm):
    """Appointment creation form"""
    
    class Meta:
        model = Appointment
        fields = ['service', 'employee', 'notes']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Service field
        self.fields['service'].queryset = Service.objects.filter(is_active=True)
        self.fields['service'].widget = forms.HiddenInput()
        self.fields['service'].required = True

        # Employee field
        self.fields['employee'].queryset = Employee.objects.filter(is_active=True)
        self.fields['employee'].widget = forms.HiddenInput()
        self.fields['employee'].required = True

        # Notes field
        self.fields['notes'].widget = forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Özel istekleriniz varsa buraya yazabilirsiniz (isteğe bağlı)...'
        })
        self.fields['notes'].required = False
        self.fields['notes'].label = "Notlar"

    def clean(self):
        cleaned_data = super().clean()
        service = cleaned_data.get('service')
        employee = cleaned_data.get('employee')
        
        # date_time POST verilerinden alınacak
        date_time_str = self.data.get('date_time')
        
        if not date_time_str:
            raise ValidationError("Tarih ve saat seçimi zorunludur.")
        
        try:
            # ISO format datetime string'i parse et
            date_time = datetime.fromisoformat(date_time_str.replace('Z', '+00:00'))
            if not timezone.is_aware(date_time):
                date_time = timezone.make_aware(date_time)
            cleaned_data['date_time'] = date_time
        except (ValueError, TypeError) as e:
            raise ValidationError(f"Geçersiz tarih/saat formatı: {str(e)}")
        
        if service and employee and date_time:
            # Temel kontroller
            if date_time <= timezone.now():
                raise ValidationError("Geçmiş tarih/saat için randevu alamazsınız.")
            
            # Minimum 2 saat sonrası kontrolü
            min_time = timezone.now() + timedelta(hours=2)
            if date_time < min_time:
                raise ValidationError("Randevu en erken 2 saat sonrası için alınabilir.")
            
            # Çalışanın bu servisi verip vermediğini kontrol et
            if not employee.services.filter(id=service.id).exists():
                raise ValidationError("Seçtiğiniz uzman bu hizmeti vermemektedir.")
            
            # Müsaitlik kontrolü
            try:
                if not is_time_slot_available(employee, date_time, service.duration):
                    raise ValidationError("Seçilen uzman bu tarih ve saatte müsait değil.")
            except Exception as e:
                logger.error(f"Müsaitlik kontrolü hatası: {str(e)}")
                raise ValidationError("Müsaitlik kontrolü sırasında bir hata oluştu.")
        
        return cleaned_data


class AppointmentRescheduleForm(forms.Form):
    new_date_time = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        label='Yeni Randevu Tarihi ve Saati'
    )
    reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Değişiklik nedeni (isteğe bağlı)...'}),
        label='Değişiklik Nedeni'
    )

    def __init__(self, *args, **kwargs):
        self.appointment = kwargs.pop('appointment', None)
        super().__init__(*args, **kwargs)
        if self.appointment:
            min_datetime = timezone.now() + timedelta(hours=2)
            self.fields['new_date_time'].widget.attrs['min'] = min_datetime.strftime('%Y-%m-%dT%H:%M')

    def clean_new_date_time(self):
        new_dt = self.cleaned_data.get('new_date_time')
        if new_dt and self.appointment:
            if new_dt <= timezone.now():
                raise ValidationError("Yeni randevu tarihi geçmişte olamaz.")
            if new_dt <= timezone.now() + timedelta(hours=1):
                raise ValidationError("Yeni randevu en az 1 saat sonraya alınabilir.")

            # Check business hours
            if not (9 <= new_dt.hour < 18):
                raise ValidationError("Seçilen saat çalışma saatleri dışındadır.")
            if new_dt.weekday() == 6:  # Sunday
                raise ValidationError("Pazar günleri kapalıyız.")

            # Check employee availability
            if not is_time_slot_available(self.appointment.employee, new_dt, self.appointment.service.duration):
                raise ValidationError("Seçtiğiniz çalışan bu yeni tarih ve saatte müsait değil.")
        return new_dt


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'service_rating', 'employee_rating', 'cleanliness_rating', 
                  'title', 'comment', 'pros', 'cons', 'would_recommend']
        widgets = {
            'rating': forms.RadioSelect(choices=[(i, '★' * i) for i in range(1, 6)]),
            'service_rating': forms.RadioSelect(choices=[(i, '★' * i) for i in range(1, 6)]),
            'employee_rating': forms.RadioSelect(choices=[(i, '★' * i) for i in range(1, 6)]),
            'cleanliness_rating': forms.RadioSelect(choices=[(i, '★' * i) for i in range(1, 6)]),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Değerlendirmeniz için bir başlık...'}),
            'comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Deneyiminizi detaylı olarak anlatın...'}),
            'pros': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Beğendiğiniz özellikler...'}),
            'cons': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'İyileştirilmesi gereken noktalar...'}),
            'would_recommend': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }
        labels = {
            'rating': 'Genel Memnuniyetiniz',
            'service_rating': 'Hizmet Kalitesi',
            'employee_rating': 'Uzman Performansı',
            'cleanliness_rating': 'Temizlik ve Hijyen',
            'title': 'Başlık',
            'comment': 'Yorumunuz',
            'pros': 'Beğendiğiniz Yönler',
            'cons': 'Geliştirilebilecek Yönler',
            'would_recommend': 'Bu salonu arkadaşlarınıza tavsiye eder misiniz?'
        }


class CustomerProfileForm(forms.ModelForm):
    class Meta:
        model = CustomerProfile
        fields = ['phone', 'birth_date', 'gender', 'address', 'preferred_employee', 
                  'allergies', 'skin_type', 'accepts_marketing', 'accepts_sms', 'notes']
        widgets = {
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+90 555 123 4567'}),
            'birth_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Adresiniz...'}),
            'allergies': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Bilinen alerjileriniz...'}),
            'skin_type': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Örn: Yağlı, Kuru, Karma...'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Size özel notlar...'}),
            'accepts_marketing': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'accepts_sms': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['preferred_employee'].queryset = Employee.objects.filter(is_active=True)
        self.fields['preferred_employee'].empty_label = "Tercih Yok"
        self.fields['preferred_employee'].widget.attrs.update({'class': 'form-select'})


class ContactForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ['name', 'email', 'phone', 'subject', 'message']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Adınız Soyadınız'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'ornek@email.com'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+90 555 123 45 67 (İsteğe Bağlı)'}),
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Mesaj konusu'}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Mesajınızı buraya yazın...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['phone'].required = False


class AppointmentSearchForm(forms.Form):
    query = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Hizmet, çalışan, not ara...'}),
        label='Arama'
    )
    service = forms.ModelChoiceField(
        queryset=Service.objects.filter(is_active=True),
        required=False, 
        empty_label="Tüm Hizmetler",
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Hizmet'
    )
    employee = forms.ModelChoiceField(
        queryset=Employee.objects.filter(is_active=True),
        required=False, 
        empty_label="Tüm Uzmanlar",
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Uzman'
    )
    status = forms.ChoiceField(
        choices=[('', 'Tüm Durumlar')] + list(Appointment.STATUS_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Durum'
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label='Başlangıç Tarihi'
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label='Bitiş Tarihi'
    )

    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')
        if date_from and date_to and date_from > date_to:
            raise ValidationError("Başlangıç tarihi, bitiş tarihinden sonra olamaz.")
        return cleaned_data


class QuickAppointmentForm(forms.Form):
    """Staff quick appointment form."""
    customer_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Müşteri Adı Soyadı'}),
        label="Müşteri Adı"
    )
    customer_phone = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+90 5xx xxx xx xx'}),
        label="Müşteri Telefonu"
    )
    service = forms.ModelChoiceField(
        queryset=Service.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Hizmet"
    )
    employee = forms.ModelChoiceField(
        queryset=Employee.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Uzman"
    )
    appointment_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="Tarih",
        initial=timezone.now().date()
    )
    appointment_time = forms.TimeField(
        widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        label="Saat",
        initial=timezone.now().strftime('%H:%M')
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Ek notlar...'}),
        label="Notlar"
    )

    def clean_customer_phone(self):
        phone = self.cleaned_data.get('customer_phone')
        if phone and not validate_phone_number_format(phone):
            raise ValidationError("Geçerli bir telefon numarası formatı girin.")
        return clean_and_format_phone_number(phone) if phone else phone

    def clean(self):
        cleaned_data = super().clean()
        app_date = cleaned_data.get('appointment_date')
        app_time = cleaned_data.get('appointment_time')
        employee = cleaned_data.get('employee')
        service = cleaned_data.get('service')

        if app_date and app_time:
            date_time = timezone.make_aware(datetime.combine(app_date, app_time))
            cleaned_data['date_time'] = date_time

            if date_time <= timezone.now():
                self.add_error(None, "Randevu geçmiş bir tarih/saat için oluşturulamaz.")

            if employee and service:
                if not is_time_slot_available(employee, date_time, service.duration):
                    self.add_error(None, "Seçilen uzman bu tarih ve saatte müsait değil.")
        return cleaned_data