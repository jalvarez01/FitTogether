# Generated migration - create Notification model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('posts', '0004_post_video_and_video_duration'),
        ('social', '0004_message_is_edited_message_updated_at'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('notif_type', models.CharField(
                    max_length=20,
                    choices=[
                        ('post', 'Friend created a post'),
                        ('like', 'Friend liked your post'),
                    ],
                )),
                ('is_read', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('recipient', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='notifications',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('actor', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='triggered_notifications',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('post', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='notifications',
                    to='posts.post',
                )),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['recipient', 'is_read'], name='social_notif_recip_idx'),
                ],
            },
        ),
    ]
