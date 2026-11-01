from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


def staff_required(view):
    """Only active staff may use the management dashboard; anonymous users go to login."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not (user.is_active and user.is_staff):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper


def content_manager_required(view):
    """Website-content editing: active staff who also hold the 'change site page' permission.

    Superusers always have it. Other staff accounts need it granted in Django admin, so not every staff member
    can rewrite the public policies.
    """

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not (user.is_active and user.is_staff and user.has_perm("core.change_sitepage")):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper
