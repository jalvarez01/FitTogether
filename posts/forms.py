from django import forms
from .models import Post


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ["content", "image"]

class PostEditForm(forms.ModelForm):
    remove_image = forms.BooleanField(required=False, initial=False, label="Remove current image")

    class Meta:
        model = Post
        fields = ["content", "image"]  # ajusta si tu campo se llama message/text/photo
        widgets = {
            "content": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def save(self, commit=True):
        post = super().save(commit=False)

        if self.cleaned_data.get("remove_image"):
            # Si el usuario marcó borrar foto
            if getattr(post, "image", None):
                post.image.delete(save=False)
                post.image = None

        if commit:
            post.save()
        return post