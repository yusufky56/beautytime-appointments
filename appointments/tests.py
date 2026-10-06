from datetime import datetime, time, timedelta

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Appointment, Employee, Service, ServiceCategory


def next_weekday_at(hour, minute=0):
    """A timezone-aware datetime on the next Monday-Friday at the given local time."""
    day = timezone.localdate() + timedelta(days=1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return timezone.make_aware(datetime.combine(day, time(hour, minute)))


class BaseData(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('ayse', password='strong-pass-123')
        cls.other = User.objects.create_user('mehmet', password='strong-pass-123')
        category = ServiceCategory.objects.create(name='Saç')
        cls.service = Service.objects.create(category=category, name='Saç Kesimi', duration=60, price=200)
        cls.employee = Employee.objects.create(
            name='Elif Demir',
            specialty='Saç',
            **{f'{d}_start': time(9) for d in ('monday', 'tuesday', 'wednesday', 'thursday', 'friday')},
            **{f'{d}_end': time(18) for d in ('monday', 'tuesday', 'wednesday', 'thursday', 'friday')},
        )
        cls.employee.services.add(cls.service)

    def book(self, user=None, at=None, **extra):
        return Appointment.objects.create(
            user=user or self.user,
            service=self.service,
            employee=self.employee,
            date_time=at or next_weekday_at(10),
            **extra,
        )


class AppointmentModelTests(BaseData):
    def test_save_fills_end_time_and_price(self):
        appt = self.book(discount=50)
        self.assertEqual(appt.end_time - appt.date_time, timedelta(minutes=60))
        self.assertEqual(appt.price, 200)
        self.assertEqual(appt.final_price, 150)

    def test_past_appointment_is_invalid(self):
        appt = Appointment(user=self.user, service=self.service, employee=self.employee,
                           date_time=timezone.now() - timedelta(hours=1))
        with self.assertRaises(ValidationError):
            appt.clean()

    def test_outside_working_hours_is_invalid(self):
        appt = Appointment(user=self.user, service=self.service, employee=self.employee,
                           date_time=next_weekday_at(20))
        with self.assertRaises(ValidationError):
            appt.clean()

    def test_working_hours_use_local_time(self):
        # 09:30 Istanbul time is 06:30 UTC; it must count as inside 09:00-18:00
        self.assertTrue(self.employee.is_available(next_weekday_at(9, 30)))

    def test_overlapping_appointment_is_rejected(self):
        self.book(at=next_weekday_at(10))
        clash = Appointment(user=self.other, service=self.service, employee=self.employee,
                            date_time=next_weekday_at(10, 30))
        with self.assertRaises(ValidationError):
            clash.clean()

    def test_back_to_back_appointment_is_allowed(self):
        self.book(at=next_weekday_at(10))
        nxt = Appointment(user=self.other, service=self.service, employee=self.employee,
                          date_time=next_weekday_at(11))
        nxt.clean()  # should not raise

    def test_cancellation_window(self):
        soon = self.book(at=timezone.now() + timedelta(hours=1))
        later = self.book(at=next_weekday_at(14) + timedelta(days=7))
        self.assertFalse(soon.can_be_cancelled())
        self.assertTrue(later.can_be_cancelled())
        later.status = 'completed'
        self.assertFalse(later.can_be_cancelled())


class ViewTests(BaseData):
    def test_public_pages(self):
        for name in ('home', 'about', 'contact', 'faq', 'service_list', 'employee_list', 'login', 'register'):
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_private_pages_require_login(self):
        for name in ('dashboard', 'appointment_list', 'appointment_create', 'profile_view'):
            with self.subTest(page=name):
                res = self.client.get(reverse(name))
                self.assertEqual(res.status_code, 302)
                self.assertIn(reverse('login'), res['Location'])

    def test_logged_in_user_sees_dashboard_and_list(self):
        self.book()
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 200)
        res = self.client.get(reverse('appointment_list'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Saç Kesimi')

    def test_user_cannot_open_someone_elses_appointment(self):
        appt = self.book(user=self.other)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('appointment_detail', args=[appt.uuid])).status_code, 404)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('appointment_detail', args=[appt.uuid])).status_code, 200)

    def test_available_times_api_validates_parameters(self):
        self.client.force_login(self.user)
        res = self.client.get(reverse('api_available_times'))
        self.assertEqual(res.status_code, 400)
