from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("shop", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="category",
            name="section",
            field=models.CharField(
                choices=[
                    ("memberships", "Абонементы"),
                    ("personal", "Персональные"),
                    ("group", "Групповые"),
                    ("other", "Прочее"),
                ],
                db_index=True,
                default="group",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="subtitle",
            field=models.CharField(blank=True, default="", max_length=160),
        ),
        migrations.AddField(
            model_name="product",
            name="badge",
            field=models.CharField(blank=True, default="", max_length=60),
        ),
        migrations.AddField(
            model_name="product",
            name="image",
            field=models.ImageField(blank=True, null=True, upload_to="shop/"),
        ),
        migrations.AddField(
            model_name="product",
            name="sort",
            field=models.PositiveIntegerField(default=100),
        ),
        migrations.AddField(
            model_name="product",
            name="is_trial",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="product",
            name="trial_scope",
            field=models.CharField(blank=True, default="", max_length=16),
        ),
        migrations.CreateModel(
            name="TrialUse",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("scope", models.CharField(max_length=16)),
                ("used_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="trial_uses", to=settings.AUTH_USER_MODEL)),
            ],
            options={"unique_together": {("user", "scope")}},
        ),
    ]
