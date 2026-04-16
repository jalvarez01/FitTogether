from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0004_profile_banner_color"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="training_reminder_days",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
        migrations.AddField(
            model_name="profile",
            name="training_reminders_enabled",
            field=models.BooleanField(default=False),
        ),
    ]