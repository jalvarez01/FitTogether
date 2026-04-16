from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Profile


class CustomUserCreationForm(UserCreationForm):
    weekly_training_days = forms.IntegerField(
        min_value=1,
        max_value=7,
        label="How many days per week do you train?",
        widget=forms.NumberInput(attrs={"min": 1, "max": 7}),
    )

    class Meta:
        model = User
        fields = ("username", "password1", "password2", "weekly_training_days")

    def save(self, commit=True):
        user = super().save(commit=commit)
        weekly_days = self.cleaned_data["weekly_training_days"]
        user.profile.weekly_training_days = weekly_days
        user.profile.save()
        return user


class ProfileSettingsForm(forms.ModelForm):
    username = forms.CharField(
        max_length=150,
        label="Username",
        widget=forms.TextInput(attrs={"placeholder": "Enter your username"}),
    )

    weekly_training_days = forms.IntegerField(
        min_value=1,
        max_value=7,
        label="Target training days per week",
        widget=forms.NumberInput(attrs={"min": 1, "max": 7}),
    )

    training_reminders_enabled = forms.BooleanField(
        required=False,
        label="Enable training reminders",
    )

    training_reminder_days = forms.MultipleChoiceField(
        required=False,
        label="Reminder days",
        choices=Profile.REMINDER_DAY_CHOICES,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = Profile
        fields = (
            "weekly_training_days",
            "training_reminders_enabled",
        )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        super().__init__(*args, **kwargs)

        self.fields["username"].initial = self.user.username
        self.fields["weekly_training_days"].initial = self.instance.weekly_training_days
        self.fields["training_reminders_enabled"].initial = self.instance.training_reminders_enabled
        self.fields["training_reminder_days"].initial = self.instance.get_training_reminder_days_list()

    def clean_username(self):
        username = self.cleaned_data["username"].strip()

        exists = User.objects.exclude(pk=self.user.pk).filter(username__iexact=username).exists()
        if exists:
            raise forms.ValidationError("This username is already taken.")

        return username

    def clean(self):
        cleaned_data = super().clean()

        reminders_enabled = cleaned_data.get("training_reminders_enabled")
        reminder_days = cleaned_data.get("training_reminder_days") or []

        if reminders_enabled and not reminder_days:
            self.add_error(
                "training_reminder_days",
                "Select at least one day if reminders are enabled.",
            )

        return cleaned_data

    def save(self, commit=True):
        profile = super().save(commit=False)

        self.user.username = self.cleaned_data["username"]
        profile.weekly_training_days = self.cleaned_data["weekly_training_days"]
        profile.training_reminders_enabled = self.cleaned_data["training_reminders_enabled"]
        profile.set_training_reminder_days_list(
            self.cleaned_data.get("training_reminder_days", [])
        )

        if commit:
            self.user.save()
            profile.save()

        return profile