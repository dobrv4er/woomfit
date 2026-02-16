from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("schedule", "0004_alter_booking_options_alter_session_options_and_more"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="session",
            index=models.Index(fields=["start_at"], name="sess_start_idx"),
        ),
        migrations.AddIndex(
            model_name="session",
            index=models.Index(fields=["location", "start_at"], name="sess_loc_start_idx"),
        ),
        migrations.AddConstraint(
            model_name="booking",
            constraint=models.UniqueConstraint(fields=("user", "session"), name="uniq_user_session"),
        ),
        migrations.AddIndex(
            model_name="booking",
            index=models.Index(fields=["user", "booking_status"], name="book_user_status_idx"),
        ),
        migrations.AddIndex(
            model_name="booking",
            index=models.Index(fields=["session", "booking_status"], name="book_sess_status_idx"),
        ),
    ]
