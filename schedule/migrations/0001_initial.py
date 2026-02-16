from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings

class Migration(migrations.Migration):
    initial = True
    dependencies = [("accounts","0001_initial")]
    operations = [
        migrations.CreateModel(
            name="Trainer",
            fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                    ("name", models.CharField(max_length=120))],
        ),
        migrations.CreateModel(
            name="Session",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=140)),
                ("start_at", models.DateTimeField()),
                ("duration_min", models.PositiveIntegerField(default=50)),
                ("location", models.CharField(blank=True, max_length=140)),
                ("capacity", models.PositiveIntegerField(default=20)),
                ("trainer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="sessions", to="schedule.trainer")),
            ],
        ),
        migrations.CreateModel(
            name="Booking",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("session", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="bookings", to="schedule.session")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={"unique_together": {("user","session")}},
        ),
    ]
