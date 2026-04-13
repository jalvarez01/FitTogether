from django import forms
from .models import Post


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ["content", "image"]

    def clean(self):
        cleaned_data = super().clean()
        content = (cleaned_data.get("content") or "").strip()
        image = cleaned_data.get("image")

        if not content and not image:
            raise forms.ValidationError(
                "A post must have at least text content or an image."
            )

        return cleaned_data


class PostEditForm(forms.ModelForm):
    remove_image = forms.BooleanField(required=False, initial=False, label="Remove current image")

    class Meta:
        model = Post
        fields = ["content", "image"]
        widgets = {
            "content": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        content = (cleaned_data.get("content") or "").strip()
        image = cleaned_data.get("image")
        remove_image = cleaned_data.get("remove_image")

        # Si va a eliminar la imagen, necesita al menos contenido
        if remove_image and not content and not image:
            raise forms.ValidationError(
                "A post must have at least text content or an image."
            )

        # Si no tiene imagen existente ni nueva ni contenido
        if not content and not image and not self.instance.image:
            raise forms.ValidationError(
                "A post must have at least text content or an image."
            )

        return cleaned_data

    def save(self, commit=True):
        post = super().save(commit=False)

        if self.cleaned_data.get("remove_image"):
            if getattr(post, "image", None):
                post.image.delete(save=False)
                post.image = None

        if commit:
            post.save()
        return post