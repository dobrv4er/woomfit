from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings

class Migration(migrations.Migration):
    initial = True
    dependencies = [("accounts","0001_initial")]
    operations = [
        migrations.CreateModel(
            name="Order",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("status", models.CharField(choices=[("new","Новый"),("payment_pending","Ожидает оплату"),("paid","Оплачен"),("canceled","Отменен")], default="new", max_length=32)),
                ("total_rub", models.PositiveIntegerField(default=0)),
                ("tb_payment_id", models.CharField(blank=True, max_length=64)),
                ("tb_status", models.CharField(blank=True, max_length=64)),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="OrderItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("product_name", models.CharField(max_length=140)),
                ("unit_price_rub", models.PositiveIntegerField(default=0)),
                ("qty", models.PositiveIntegerField(default=1)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="orders.order")),
            ],
        ),
    ]
