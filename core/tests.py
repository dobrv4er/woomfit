from datetime import datetime, time, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from schedule.models import Session, Trainer


class RentPrivacyTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(username="owner", password="pass12345")
        self.other = user_model.objects.create_user(username="other", password="pass12345")

        self.location = settings.WOOMFIT_LOCATIONS[0]
        self.trainer = Trainer.objects.create(name="Rent trainer")

        slot_day = timezone.localdate() + timedelta(days=1)
        tz = timezone.get_current_timezone()
        self.slot_start = timezone.make_aware(datetime.combine(slot_day, time(hour=10, minute=0)), tz)
        self.slot_key = timezone.localtime(self.slot_start).strftime("%Y-%m-%dT%H:%M")

        Session.objects.create(
            title="Rent owner slot",
            kind=Session.Kind.RENT,
            client=self.owner,
            start_at=self.slot_start,
            duration_min=60,
            location=self.location,
            trainer=self.trainer,
            capacity=1,
        )

    @staticmethod
    def _find_slot_state(rows, slot_key: str) -> str | None:
        for row in rows:
            for cell in row.get("cells", []):
                if cell.get("key") == slot_key:
                    return cell.get("state")
        return None

    def test_owner_sees_own_paid_rent_details(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("core:rent"))
        self.assertEqual(response.status_code, 200)

        rows = response.context["rows"]
        slot_state = self._find_slot_state(rows, self.slot_key)
        self.assertEqual(slot_state, "rent_paid")

        booked_slots = response.context["booked_slots"]
        self.assertEqual(len(booked_slots), 1)
        self.assertTrue(response.context["show_paid_rent_details"])
        self.assertTrue(response.context["show_my_paid_rent_legend"])

    def test_other_user_sees_slot_only_as_busy(self):
        self.client.force_login(self.other)
        response = self.client.get(reverse("core:rent"))
        self.assertEqual(response.status_code, 200)

        rows = response.context["rows"]
        slot_state = self._find_slot_state(rows, self.slot_key)
        self.assertEqual(slot_state, "busy")

        self.assertEqual(response.context["booked_slots"], [])
        self.assertTrue(response.context["show_paid_rent_details"])
        self.assertFalse(response.context["show_my_paid_rent_legend"])

    def test_anonymous_user_sees_slot_busy_without_paid_block(self):
        response = self.client.get(reverse("core:rent"))
        self.assertEqual(response.status_code, 200)

        rows = response.context["rows"]
        slot_state = self._find_slot_state(rows, self.slot_key)
        self.assertEqual(slot_state, "busy")

        self.assertEqual(response.context["booked_slots"], [])
        self.assertFalse(response.context["show_paid_rent_details"])
        self.assertFalse(response.context["show_my_paid_rent_legend"])
