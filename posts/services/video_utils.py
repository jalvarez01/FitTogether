import os
import tempfile

from django.core.exceptions import ValidationError


MAX_VIDEO_DURATION_SECONDS = 30
ALLOWED_VIDEO_CONTENT_TYPES = {
    "video/mp4",
    "video/quicktime",
    "video/x-m4v",
    "video/webm",
}


def _get_video_file_clip_class():
    """
    MoviePy 2.x imports VideoFileClip from moviepy.
    Older MoviePy 1.x imports it from moviepy.editor.
    This helper supports both, so the project is less fragile.
    """
    try:
        from moviepy import VideoFileClip
        return VideoFileClip
    except Exception:
        from moviepy.editor import VideoFileClip
        return VideoFileClip


def get_uploaded_video_duration(uploaded_file):
    """
    Return duration in seconds for a Django UploadedFile.
    The uploaded file is copied to a temporary file because MoviePy needs a path.
    """
    VideoFileClip = _get_video_file_clip_class()
    suffix = os.path.splitext(uploaded_file.name or "")[1] or ".mp4"
    temp_path = None

    try:
        current_position = uploaded_file.tell()
    except Exception:
        current_position = 0

    try:
        uploaded_file.seek(0)
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_path = temp_file.name
            for chunk in uploaded_file.chunks():
                temp_file.write(chunk)

        clip = VideoFileClip(temp_path)
        try:
            return float(clip.duration or 0)
        finally:
            clip.close()
    finally:
        try:
            uploaded_file.seek(current_position)
        except Exception:
            pass
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


def validate_video_file(uploaded_file):
    if not uploaded_file:
        return None

    content_type = getattr(uploaded_file, "content_type", "")
    if content_type and content_type not in ALLOWED_VIDEO_CONTENT_TYPES:
        raise ValidationError("Only MP4, MOV, M4V, or WEBM videos are allowed.")

    try:
        duration = get_uploaded_video_duration(uploaded_file)
    except Exception:
        raise ValidationError("Could not read this video. Please upload a valid video file.")

    if duration > MAX_VIDEO_DURATION_SECONDS:
        raise ValidationError("Videos must be 30 seconds or shorter.")

    return duration
