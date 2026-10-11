from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm, UserChangeForm, UserCreationForm
from django.utils.translation import gettext_lazy as _

from .models import User


class ClinicAuthenticationForm(AuthenticationForm):
    """
    Formulaire de connexion personnalisé utilisant l'adresse email.
    """

    username = forms.EmailField(
        label=_("Adresse email"),
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "ex: dr.dupont@clinique.fr",
                "autocomplete": "email",
                "autofocus": True,
                "id": "id_email",
            }
        ),
    )
    password = forms.CharField(
        label=_("Mot de passe"),
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Votre mot de passe",
                "autocomplete": "current-password",
                "id": "id_password",
            }
        ),
    )

    error_messages = {
        "invalid_login": _(
            "Adresse email ou mot de passe incorrect. "
            "Veuillez vérifier vos identifiants ou contacter l'administration de la clinique."
        ),
        "inactive": _("Ce compte est actuellement inactif. Contactez l'administrateur."),
    }

    def clean(self):
        email = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")

        if email and password:
            self.user_cache = authenticate(
                self.request,
                username=email,
                password=password,
            )
            if self.user_cache is None:
                raise self.get_invalid_login_error()
            else:
                self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data


class ClinicUserCreationForm(UserCreationForm):
    """
    Formulaire de création d'utilisateur pour l'administration.
    """

    class Meta:
        model = User
        fields = ("email", "first_name", "last_name", "role", "specialty", "phone_number")


class ClinicUserChangeForm(UserChangeForm):
    """
    Formulaire de modification d'utilisateur pour l'administration.
    """

    class Meta:
        model = User
        fields = ("email", "first_name", "last_name", "role", "specialty", "phone_number", "is_active", "is_staff")
