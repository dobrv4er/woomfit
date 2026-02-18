from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("schedule", "0009_workout"),
    ]

    operations = [
        migrations.AddField(
            model_name="paymentintent",
            name="legal_accept_ip",
            field=models.GenericIPAddressField(blank=True, null=True, verbose_name="Юр. согласие: IP"),
        ),
        migrations.AddField(
            model_name="paymentintent",
            name="legal_accepted_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Юр. согласие: дата"),
        ),
    ]
