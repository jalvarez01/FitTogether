from django import forms
from .models import Post
from .services.video_utils import validate_video_file


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ["content", "image", "video"]

    def clean(self):
        cleaned_data = super().clean()
        content = (cleaned_data.get("content") or "").strip()
        image = cleaned_data.get("image")
        video = cleaned_data.get("video")

        if image and video:
            raise forms.ValidationError("Please upload either an image or a video, not both.")

        if not content and not image and not video:
            raise forms.ValidationError(
                "A post must have at least text content, an image, or a video."
            )

        if video:
            cleaned_data["video_duration"] = validate_video_file(video)

        return cleaned_data


class PostEditForm(forms.ModelForm):
    remove_image = forms.BooleanField(required=False, initial=False, label="Remove current image")
    remove_video = forms.BooleanField(required=False, initial=False, label="Remove current video")

    class Meta:
        model = Post
        fields = ["content", "image", "video"]
        widgets = {
            "content": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        content = (cleaned_data.get("content") or "").strip()
        image = cleaned_data.get("image")
        video = cleaned_data.get("video")
        remove_image = cleaned_data.get("remove_image")
        remove_video = cleaned_data.get("remove_video")

        current_image_kept = bool(self.instance.image) and not remove_image
        current_video_kept = bool(self.instance.video) and not remove_video

        if image and (video or current_video_kept):
            raise forms.ValidationError("Please use either an image or a video, not both.")

        if video and (image or current_image_kept):
            raise forms.ValidationError("Please use either an image or a video, not both.")

        if not content and not image and not video and not current_image_kept and not current_video_kept:
            raise forms.ValidationError(
                "A post must have at least text content, an image, or a video."
            )

        if video:
            cleaned_data["video_duration"] = validate_video_file(video)

        return cleaned_data

    def save(self, commit=True):
        post = super().save(commit=False)

        if self.cleaned_data.get("remove_image") and getattr(post, "image", None):
            post.image.delete(save=False)
            post.image = None

        if self.cleaned_data.get("remove_video") and getattr(post, "video", None):
            post.video.delete(save=False)
            post.video = None
            post.video_duration = None

        if self.cleaned_data.get("video"):
            post.video_duration = self.cleaned_data.get("video_duration")

        if self.cleaned_data.get("image"):
            post.video = None
            post.video_duration = None

        if self.cleaned_data.get("video"):
            post.image = None

        if commit:
            post.save()
        return post