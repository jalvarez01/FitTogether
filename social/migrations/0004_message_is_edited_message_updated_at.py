# Generated migration - add is_edited and updated_at to Message

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('social', '0003_message'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='is_edited',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='message',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
