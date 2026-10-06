# create_test_users.py
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'randevu_sistemi.settings')
django.setup()

from django.contrib.auth.models import User
from appointments.models import CustomerProfile

def create_test_users():
    # Test kullanıcıları
    test_users = [
        {
            'username': 'demo',
            'password': 'demo123',
            'email': 'demo@beautytime.com',
            'first_name': 'Demo',
            'last_name': 'Kullanıcı',
            'phone': '+905551234567'
        },
        {
            'username': 'ahmet',
            'password': 'ahmet123',
            'email': 'ahmet@example.com', 
            'first_name': 'Ahmet',
            'last_name': 'Yılmaz',
            'phone': '+905559876543'
        }
    ]
    
    for user_data in test_users:
        username = user_data.pop('username')
        password = user_data.pop('password')
        phone = user_data.pop('phone')
        
        # Kullanıcı oluştur veya getir
        user, created = User.objects.get_or_create(
            username=username,
            defaults=user_data
        )
        
        if created:
            user.set_password(password)
            user.save()
            
            # Profil oluştur
            CustomerProfile.objects.create(
                user=user,
                phone=phone,
                accepts_marketing=True,
                accepts_sms=True
            )
            
            print(f"✅ Kullanıcı oluşturuldu: {username} / {password}")
        else:
            print(f"ℹ️  Kullanıcı zaten mevcut: {username}")
    
    # Staff kullanıcı
    staff_user, created = User.objects.get_or_create(
        username='staff',
        defaults={
            'email': 'staff@beautytime.com',
            'first_name': 'Staff',
            'last_name': 'User',
            'is_staff': True
        }
    )
    
    if created:
        staff_user.set_password('staff123')
        staff_user.save()
        print("✅ Staff kullanıcı oluşturuldu: staff / staff123")
    else:
        print("ℹ️  Staff kullanıcı zaten mevcut: staff")

if __name__ == '__main__':
    create_test_users()