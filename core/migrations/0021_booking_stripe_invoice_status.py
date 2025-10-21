from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0020_booking_schedule_link"),
    ]

    operations = [
        migrations.AddField(
            model_name="booking",
            name="stripe_invoice_status",
            field=models.CharField(max_length=32, blank=True, null=True),
        ),
    ]
