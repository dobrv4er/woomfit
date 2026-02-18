from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from memberships.models import Membership


class MembershipActivationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="u1",
            password="pass12345",
        )

    def test_time_membership_becomes_active_on_first_usage(self):
        m = Membership.objects.create(
            user=self.user,
            title="Месячный",
            kind=Membership.Kind.TIME,
            scope=Membership.Scope.GROUP,
            validity_days=30,
            is_active=True,
        )

        self.assertTrue(m.is_pending_activation())
        self.assertFalse(m.active_by_date())
        self.assertTrue(m.can_book_group())

        self.assertTrue(m.consume_visit())
        m.refresh_from_db()

        today = timezone.localdate()
        self.assertFalse(m.is_pending_activation())
        self.assertEqual(m.start_date, today)
        self.assertEqual(m.end_date, today + timedelta(days=29))
        self.assertTrue(m.active_by_date())
        self.assertTrue(m.can_book_group())

    def test_visits_membership_with_validity_starts_on_first_charge(self):
        m = Membership.objects.create(
            user=self.user,
            title="10 посещений",
            kind=Membership.Kind.VISITS,
            scope=Membership.Scope.GROUP,
            total_visits=10,
            left_visits=10,
            validity_days=60,
            is_active=True,
        )

        self.assertTrue(m.is_pending_activation())
        self.assertFalse(m.active_by_date())
        self.assertTrue(m.can_book_group())

        self.assertTrue(m.consume_visit())
        m.refresh_from_db()

        today = timezone.localdate()
        self.assertEqual(m.left_visits, 9)
        self.assertEqual(m.start_date, today)
        self.assertEqual(m.end_date, today + timedelta(days=59))

    def test_membership_without_validity_days_works_as_before(self):
        m = Membership.objects.create(
            user=self.user,
            title="Без срока",
            kind=Membership.Kind.VISITS,
            scope=Membership.Scope.GROUP,
            total_visits=5,
            left_visits=5,
            is_active=True,
        )

        self.assertFalse(m.is_pending_activation())
        self.assertTrue(m.active_by_date())
        self.assertTrue(m.can_book_group())
