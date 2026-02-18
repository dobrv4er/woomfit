from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0002_order_fulfilled_and_item_product"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="legal_accept_ip",
            field=models.GenericIPAddressField(blank=True, null=True, verbose_name="Юр. согласие: IP"),
        ),
        migrations.AddField(
            model_name="order",
            name="legal_accepted_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Юр. согласие: дата"),
        ),
    ]
