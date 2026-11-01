import re

CODE_RE = re.compile(r"^[A-Za-z0-9]{3,20}$")


class ReferralCaptureMiddleware:
    """Remember ?ref=CODE in the session so registration can attribute the referral.

    Visiting a link never earns anything; it only pre-fills the registration form.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        code = request.GET.get("ref", "")
        if code and CODE_RE.match(code):
            request.session["referral_code"] = code.upper()
        return self.get_response(request)
