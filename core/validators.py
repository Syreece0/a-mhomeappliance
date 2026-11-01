from django.conf import settings
from django.core.exceptions import ValidationError


def validate_image_size(file):
    limit = getattr(settings, "MAX_IMAGE_UPLOAD_MB", 5) * 1024 * 1024
    if file.size > limit:
        raise ValidationError(f"Image is too large (max {settings.MAX_IMAGE_UPLOAD_MB} MB).")
