# Migración para agregar el tipo 'comment' a Notification.notif_type

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('social', '0005_notification'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='notif_type',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('post', 'Friend created a post'),
                    ('like', 'Friend liked your post'),
                    ('comment', 'Friend commented on your post'),
                ],
            ),
        ),
    ]