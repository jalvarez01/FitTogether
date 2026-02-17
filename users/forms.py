from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm

class CustomUserCreationForm(UserCreationForm):
    weekly_training_days = forms.IntegerField(
        min_value=1,
        max_value=7,
        label="How many days per week do you train?"
    )

    class Meta:
        model = User
        fields = ("username", "password1", "password2", "weekly_training_days")

    def save(self, commit=True):
        user = super().save(commit=commit)

        # IMPORTANT: el profile ya lo crea el signal
        weekly_days = self.cleaned_data["weekly_training_days"]
        user.profile.weekly_training_days = weekly_days
        user.profile.save()

        return user

# Formulario: Actualiza profile ya creado por signal