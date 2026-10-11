from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import (
    LoginView,
    PasswordChangeDoneView,
    PasswordChangeView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import TemplateView

from .forms import ClinicAuthenticationForm


class ClinicLoginView(LoginView):
    """
    Vue de connexion pour le personnel de la clinique.
    """
    authentication_form = ClinicAuthenticationForm
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse_lazy("accounts:dashboard")

    def form_valid(self, form):
        user = form.get_user()
        messages.success(
            self.request,
            _(f"Bienvenue, {user.get_full_name() or user.email} ({user.get_role_display()})."),
        )
        return super().form_valid(form)


class ClinicLogoutView(View):
    """
    Vue de déconnexion personnalisée.
    """
    def post(self, request, *args, **kwargs):
        logout(request)
        messages.info(request, _("Vous avez été déconnecté avec succès."))
        return redirect("accounts:login")

    def get(self, request, *args, **kwargs):
        # Supporte également un appel GET direct pour plus de fluidité
        logout(request)
        messages.info(request, _("Vous avez été déconnecté avec succès."))
        return redirect("accounts:login")


class DashboardView(LoginRequiredMixin, TemplateView):
    """
    Tableau de bord d'accueil après authentification,
    adapté dynamiquement selon le rôle du personnel médical ou administratif.
    """
    template_name = "accounts/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context["user_role"] = user.role
        context["user_role_label"] = user.get_role_display()
        return context


class ClinicPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("accounts:password_change_done")

    def form_valid(self, form):
        messages.success(self.request, _("Votre mot de passe a été modifié avec succès."))
        return super().form_valid(form)


class ClinicPasswordChangeDoneView(LoginRequiredMixin, PasswordChangeDoneView):
    template_name = "accounts/password_change_done.html"


class ClinicPasswordResetView(PasswordResetView):
    template_name = "accounts/password_reset.html"
    email_template_name = "accounts/password_reset_email.html"
    subject_template_name = "accounts/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")


class ClinicPasswordResetDoneView(PasswordResetDoneView):
    template_name = "accounts/password_reset_done.html"


class ClinicPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    success_url = reverse_lazy("accounts:password_reset_complete")


class ClinicPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = "accounts/password_reset_complete.html"
