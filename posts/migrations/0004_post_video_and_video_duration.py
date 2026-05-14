# Generated manually for video posts support

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('posts', '0003_post_moderation_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='video',
            field=models.FileField(blank=True, null=True, upload_to='posts/videos/'),
        ),
        migrations.AddField(
            model_name='post',
            name='video_duration',
            field=models.FloatField(blank=True, null=True),
        ),
    ]
