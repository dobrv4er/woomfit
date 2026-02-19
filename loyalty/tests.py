from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from wallet.services import get_wallet, topup

from .models import CashbackBonus, CashbackBonusSpend
from .services import (
    build_bonus_payment_plan,
    get_bonus_balance,
    grant_cashback,
    pay_with_wallet_bonus,
)


class CashbackTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="cashback-user", password="pass12345")

    def test_grant_cashback_is_idempotent_per_source(self):
        first = grant_cashback(
            user=self.user,
            base_amount=Decimal("1000.00"),
            source_type="order",
            source_id=101,
        )
        second = grant_cashback(
            user=self.user,
            base_amount=Decimal("7000.00"),
            source_type="order",
            source_id=101,
        )

        self.assertIsNotNone(first)
        self.assertEqual(first.id, second.id)
        self.assertEqual(CashbackBonus.objects.count(), 1)
        first.refresh_from_db()
        self.assertEqual(first.amount, Decimal("50.00"))

    def test_bonus_plan_applies_30_percent_cap(self):
        grant_cashback(
            user=self.user,
            base_amount=Decimal("10000.00"),  # cashback = 500
            source_type="order",
            source_id=1,
        )
        plan = build_bonus_payment_plan(
            user=self.user,
            total_amount=Decimal("1000.00"),
            bonus_eligible_amount=Decimal("1000.00"),
        )

        self.assertEqual(plan["bonus_available"], Decimal("500.00"))
        self.assertEqual(plan["bonus_cap"], Decimal("300.00"))
        self.assertEqual(plan["bonus_used"], Decimal("300.00"))
        self.assertEqual(plan["cash_needed"], Decimal("700.00"))

    def test_wallet_payment_spends_bonus_then_wallet_cash(self):
        topup(self.user, Decimal("1000.00"), reason="Test topup")
        bonus = CashbackBonus.objects.create(
            user=self.user,
            source_type="seed",
            source_id=1,
            base_amount=Decimal("0.00"),
            amount=Decimal("250.00"),
            remaining_amount=Decimal("250.00"),
            reason="Seed bonus",
            expires_at=timezone.now() + timedelta(days=30),
        )

        result = pay_with_wallet_bonus(
            user=self.user,
            total_amount=Decimal("1000.00"),
            bonus_eligible_amount=Decimal("1000.00"),
            reason="Session payment",
            source_type="session_wallet",
            source_id=555,
        )

        self.assertEqual(result["bonus_used"], Decimal("250.00"))
        self.assertEqual(result["cash_needed"], Decimal("750.00"))

        bonus.refresh_from_db()
        self.assertEqual(bonus.remaining_amount, Decimal("0.00"))

        wallet = get_wallet(self.user)
        self.assertEqual(wallet.balance, Decimal("250.00"))
        self.assertEqual(
            CashbackBonusSpend.objects.filter(user=self.user, source_type="session_wallet", source_id=555).count(),
            1,
        )
        self.assertEqual(get_bonus_balance(self.user), Decimal("0.00"))

    def test_expired_bonuses_not_in_balance(self):
        CashbackBonus.objects.create(
            user=self.user,
            source_type="seed",
            source_id=11,
            base_amount=Decimal("0.00"),
            amount=Decimal("80.00"),
            remaining_amount=Decimal("80.00"),
            expires_at=timezone.now() - timedelta(days=1),
        )
        CashbackBonus.objects.create(
            user=self.user,
            source_type="seed",
            source_id=12,
            base_amount=Decimal("0.00"),
            amount=Decimal("20.00"),
            remaining_amount=Decimal("20.00"),
            expires_at=timezone.now() + timedelta(days=10),
        )

        self.assertEqual(get_bonus_balance(self.user), Decimal("20.00"))
