from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_profile_current_weekly_streak_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='banner_color',
            field=models.CharField(default='#efeff1', max_length=20),
        ),
    ]