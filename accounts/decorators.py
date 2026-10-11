from functools import wraps
from django.contrib import messages
from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _


def role_required(allowed_roles, redirect_url="accounts:dashboard"):
    """
    Décorateur qui restreint l'accès aux utilisateurs ayant un des rôles autorisés.
    Si l'utilisateur est superutilisateur, l'accès est toujours accordé.
    """
    if isinstance(allowed_roles, str):
        allowed_roles = [allowed_roles]

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("accounts:login")

            if request.user.is_superuser or request.user.role in allowed_roles:
                return view_func(request, *args, **kwargs)

            messages.error(
                request,
                _("Accès refusé : vous n'avez pas les autorisations nécessaires pour cette section."),
            )
            return redirect(redirect_url)

        return _wrapped_view

    return decorator


def admin_required(view_func):
    """Accès réservé aux administrateurs de la clinique ou superutilisateurs."""
    return role_required(["ADMIN"])(view_func)


def doctor_required(view_func):
    """Accès réservé aux médecins/praticiens ou administrateurs."""
    return role_required(["DOCTOR", "ADMIN"])(view_func)


def nurse_required(view_func):
    """Accès réservé aux infirmiers ou administrateurs."""
    return role_required(["NURSE", "ADMIN"])(view_func)


def secretary_required(view_func):
    """Accès réservé aux secrétaires médicales ou administrateurs."""
    return role_required(["SECRETARY", "ADMIN"])(view_func)


class RoleRequiredMixin(AccessMixin):
    """
    Mixin pour les vues basées sur les classes (CBV) pour restreindre par rôle.
    """
    allowed_roles = []
    redirect_url = "accounts:dashboard"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        if request.user.is_superuser or request.user.role in self.allowed_roles:
            return super().dispatch(request, *args, **kwargs)

        messages.error(
            request,
            _("Accès refusé : vous n'avez pas les permissions requises pour cette page."),
        )
        return redirect(self.redirect_url)
