from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError


class StaffLoginForm(AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        "not_staff": "Admin access is required for this page.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Email address"
        self.fields["username"].widget.attrs.update(
            {
                "class": "form-input",
                "placeholder": "admin@xpertforma.com",
                "autocomplete": "username",
            }
        )
        self.fields["password"].widget.attrs.update(
            {
                "class": "form-input",
                "placeholder": "Enter your password",
                "autocomplete": "current-password",
                "data-password-input": "true",
            }
        )

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_staff:
            raise ValidationError(
                self.error_messages["not_staff"],
                code="not_staff",
            )
