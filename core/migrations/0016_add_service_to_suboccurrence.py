# Generated migration for SubOccurrence service link

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0015_add_service_and_links'),
    ]

    operations = [
        migrations.AddField(
            model_name='suboccurrence',
            name='service',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='core.service', help_text="Service for this occurrence; determines duration for generated booking."),
        ),
    ]
