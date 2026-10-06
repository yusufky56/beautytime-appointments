import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'randevu_sistemi.settings')
django.setup()

from appointments.models import ServiceCategory, Service, Employee, BusinessHours, FAQ
from datetime import time

def load_initial_data():
    # Service Categories
    categories = [
        {'name': 'Saç Hizmetleri', 'icon': 'fas fa-cut', 'color': '#667eea', 'order': 1},
        {'name': 'Cilt Bakımı', 'icon': 'fas fa-spa', 'color': '#f093fb', 'order': 2},
        {'name': 'Manikür & Pedikür', 'icon': 'fas fa-hand-sparkles', 'color': '#4facfe', 'order': 3},
        {'name': 'Makyaj', 'icon': 'fas fa-palette', 'color': '#fa709a', 'order': 4},
    ]
    
    for cat_data in categories:
        category, created = ServiceCategory.objects.get_or_create(
            name=cat_data['name'],
            defaults={
                'icon': cat_data['icon'],
                'color': cat_data['color'],
                'order': cat_data['order'],
                'is_active': True
            }
        )
        if created:
            print(f"Created category: {category.name}")
    
    # Services
    hair_category = ServiceCategory.objects.get(name='Saç Hizmetleri')
    skin_category = ServiceCategory.objects.get(name='Cilt Bakımı')
    nail_category = ServiceCategory.objects.get(name='Manikür & Pedikür')
    makeup_category = ServiceCategory.objects.get(name='Makyaj')
    
    services = [
        # Saç Hizmetleri
        {'category': hair_category, 'name': 'Kadın Saç Kesimi', 'duration': 60, 'price': 250},
        {'category': hair_category, 'name': 'Erkek Saç Kesimi', 'duration': 30, 'price': 150},
        {'category': hair_category, 'name': 'Saç Boyama', 'duration': 120, 'price': 400},
        {'category': hair_category, 'name': 'Ombre/Balyaj', 'duration': 180, 'price': 800},
        {'category': hair_category, 'name': 'Keratin Bakımı', 'duration': 90, 'price': 600},
        
        # Cilt Bakımı
        {'category': skin_category, 'name': 'Klasik Cilt Bakımı', 'duration': 60, 'price': 300},
        {'category': skin_category, 'name': 'Hydrafacial', 'duration': 75, 'price': 500},
        {'category': skin_category, 'name': 'Anti-Aging Bakım', 'duration': 90, 'price': 700},
        {'category': skin_category, 'name': 'Akne Bakımı', 'duration': 60, 'price': 400},
        
        # Manikür & Pedikür
        {'category': nail_category, 'name': 'Klasik Manikür', 'duration': 45, 'price': 100},
        {'category': nail_category, 'name': 'Kalıcı Oje', 'duration': 60, 'price': 200},
        {'category': nail_category, 'name': 'Klasik Pedikür', 'duration': 60, 'price': 150},
        {'category': nail_category, 'name': 'Nail Art', 'duration': 90, 'price': 300},
        
        # Makyaj
        {'category': makeup_category, 'name': 'Günlük Makyaj', 'duration': 45, 'price': 250},
        {'category': makeup_category, 'name': 'Gece Makyajı', 'duration': 60, 'price': 350},
        {'category': makeup_category, 'name': 'Gelin Makyajı', 'duration': 120, 'price': 1000},
    ]
    
    created_services = []
    for svc_data in services:
        service, created = Service.objects.get_or_create(
            name=svc_data['name'],
            category=svc_data['category'],
            defaults={
                'duration': svc_data['duration'],
                'price': svc_data['price'],
                'description': f"{svc_data['name']} hizmeti profesyonel ekibimiz tarafından sunulmaktadır.",
                'is_active': True,
                'slug': svc_data['name'].lower().replace(' ', '-').replace('ı', 'i').replace('ü', 'u').replace('ö', 'o').replace('ş', 's').replace('ğ', 'g').replace('ç', 'c')
            }
        )
        created_services.append(service)
        if created:
            print(f"Created service: {service.name}")
    
    # Employees
    employees_data = [
        {'name': 'Ayşe Yılmaz', 'title': 'Kuaför', 'specialty': 'Saç Kesimi ve Boyama'},
        {'name': 'Mehmet Kaya', 'title': 'Kuaför', 'specialty': 'Erkek Saç Kesimi'},
        {'name': 'Fatma Demir', 'title': 'Güzellik Uzmanı', 'specialty': 'Cilt Bakımı'},
        {'name': 'Zeynep Aydın', 'title': 'Nail Artist', 'specialty': 'Manikür & Pedikür'},
        {'name': 'Elif Öztürk', 'title': 'Makyöz', 'specialty': 'Profesyonel Makyaj'},
    ]
    
    for emp_data in employees_data:
        employee, created = Employee.objects.get_or_create(
            name=emp_data['name'],
            defaults={
                'title': emp_data['title'],
                'specialty': emp_data['specialty'],
                'bio': f"{emp_data['name']}, {emp_data['specialty']} alanında uzman personelimizdir.",
                'is_active': True,
                # Working hours (Monday-Saturday 9:00-18:00)
                'monday_start': time(9, 0),
                'monday_end': time(18, 0),
                'tuesday_start': time(9, 0),
                'tuesday_end': time(18, 0),
                'wednesday_start': time(9, 0),
                'wednesday_end': time(18, 0),
                'thursday_start': time(9, 0),
                'thursday_end': time(18, 0),
                'friday_start': time(9, 0),
                'friday_end': time(18, 0),
                'saturday_start': time(10, 0),
                'saturday_end': time(16, 0),
            }
        )
        
        # Assign services to employees based on their specialty
        if created:
            if 'Saç' in emp_data['specialty']:
                employee.services.add(*Service.objects.filter(category__name='Saç Hizmetleri'))
            elif 'Cilt' in emp_data['specialty']:
                employee.services.add(*Service.objects.filter(category__name='Cilt Bakımı'))
            elif 'Manikür' in emp_data['specialty']:
                employee.services.add(*Service.objects.filter(category__name='Manikür & Pedikür'))
            elif 'Makyaj' in emp_data['specialty']:
                employee.services.add(*Service.objects.filter(category__name='Makyaj'))
            
            print(f"Created employee: {employee.name}")
    
    # Business Hours
    business_hours = [
        {'day_of_week': 0, 'open_time': time(9, 0), 'close_time': time(18, 0), 'is_open': True},  # Monday
        {'day_of_week': 1, 'open_time': time(9, 0), 'close_time': time(18, 0), 'is_open': True},  # Tuesday
        {'day_of_week': 2, 'open_time': time(9, 0), 'close_time': time(18, 0), 'is_open': True},  # Wednesday
        {'day_of_week': 3, 'open_time': time(9, 0), 'close_time': time(18, 0), 'is_open': True},  # Thursday
        {'day_of_week': 4, 'open_time': time(9, 0), 'close_time': time(18, 0), 'is_open': True},  # Friday
        {'day_of_week': 5, 'open_time': time(10, 0), 'close_time': time(16, 0), 'is_open': True},  # Saturday
        {'day_of_week': 6, 'open_time': None, 'close_time': None, 'is_open': False},  # Sunday
    ]
    
    for bh_data in business_hours:
        bh, created = BusinessHours.objects.get_or_create(
            day_of_week=bh_data['day_of_week'],
            defaults={
                'open_time': bh_data['open_time'],
                'close_time': bh_data['close_time'],
                'is_open': bh_data['is_open']
            }
        )
        if created:
            days = ['Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi', 'Pazar']
            print(f"Created business hours for {days[bh_data['day_of_week']]}")
    
    # FAQs
    faqs = [
        {
            'question': 'Randevu almak için ne yapmam gerekiyor?',
            'answer': 'Web sitemizden üye girişi yaptıktan sonra "Randevu Al" butonuna tıklayarak hizmet, uzman ve tarih seçimi yapabilirsiniz.',
            'category': 'Randevu',
            'order': 1
        },
        {
            'question': 'Randevumu iptal edebilir miyim?',
            'answer': 'Evet, randevunuzdan en az 2 saat önce iptal edebilirsiniz. Randevularım sayfasından ilgili randevuyu bulup iptal edebilirsiniz.',
            'category': 'Randevu',
            'order': 2
        },
        {
            'question': 'Ödeme nasıl yapılıyor?',
            'answer': 'Ödemelerinizi salonumuzda nakit veya kredi kartı ile yapabilirsiniz. Online ödeme sistemimiz yakında hizmete girecektir.',
            'category': 'Ödeme',
            'order': 3
        },
        {
            'question': 'Hangi saatlerde açıksınız?',
            'answer': 'Pazartesi-Cuma 09:00-18:00, Cumartesi 10:00-16:00 saatleri arasında hizmet vermekteyiz. Pazar günleri kapalıyız.',
            'category': 'Genel',
            'order': 4
        },
    ]
    
    for faq_data in faqs:
        faq, created = FAQ.objects.get_or_create(
            question=faq_data['question'],
            defaults={
                'answer': faq_data['answer'],
                'category': faq_data['category'],
                'order': faq_data['order'],
                'is_active': True
            }
        )
        if created:
            print(f"Created FAQ: {faq.question[:50]}...")
    
    print("\nInitial data loading completed!")

if __name__ == '__main__':
    load_initial_data()