# Generated migration for Service model and Booking link

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0014_client_email_unique'),
    ]

    operations = [
        migrations.CreateModel(
            name='Service',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.SlugField(max_length=50, unique=True, help_text="Short code used by schedules/subscriptions (e.g., 'walk30').")),
                ('name', models.CharField(max_length=120)),
                ('duration_minutes', models.PositiveIntegerField(blank=True, null=True, help_text="Length in minutes. Must be set before auto-bookings can be created.")),
                ('is_active', models.BooleanField(default=True)),
            ],
        ),
        migrations.AddField(
            model_name='booking',
            name='service',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='core.service'),
        ),
    ]
