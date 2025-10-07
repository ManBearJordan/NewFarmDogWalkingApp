from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0008_servicedefaults_booking_block_label_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='booking',
            name='payment_intent_id',
            field=models.CharField(max_length=128, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='booking',
            name='charge_id',
            field=models.CharField(max_length=128, null=True, blank=True),
        ),
    ]
