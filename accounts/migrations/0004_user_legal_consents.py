from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_user_full_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="offer_consent_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Согласие с офертой: дата"),
        ),
        migrations.AddField(
            model_name="user",
            name="offer_consent_ip",
            field=models.GenericIPAddressField(blank=True, null=True, verbose_name="Согласие с офертой: IP"),
        ),
        migrations.AddField(
            model_name="user",
            name="personal_data_consent_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Согласие ПДн: дата"),
        ),
        migrations.AddField(
            model_name="user",
            name="personal_data_consent_ip",
            field=models.GenericIPAddressField(blank=True, null=True, verbose_name="Согласие ПДн: IP"),
        ),
    ]
