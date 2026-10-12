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
from django.db.models import F, Sum
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import TemplateView

from billing.models import Invoice, InvoicePayment, Patient
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
    Fournit les statistiques de caisse et impayés pour la secrétaire et la direction.
    """
    template_name = "accounts/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context["user_role"] = user.role
        context["user_role_label"] = user.get_role_display()

        today = timezone.localdate()

        # Indicateurs clés pour le Secrétariat / Caisse et l'Administration
        if user.is_secretary or user.is_admin_role:
            invoices_today = Invoice.objects.filter(created_at__date=today)

            # Montant encaissé aujourd'hui = total des encaissements et règlements perçus ce jour
            today_collected = InvoicePayment.objects.filter(created_at__date=today).aggregate(
                total=Sum("amount_paid")
            )["total"]
            if today_collected is None:
                today_collected = invoices_today.aggregate(
                    total=Sum(F("amount_received") - F("amount_change"))
                )["total"] or 0

            # Nombre de patients enregistrés aujourd'hui
            today_patients_count = Patient.objects.filter(created_at__date=today).count()

            # Factures non soldées (reste à payer > 0)
            unpaid_invoices = Invoice.objects.filter(amount_remaining__gt=0).select_related(
                "patient", "specialty"
            ).order_by("-created_at")

            total_unpaid_remaining = unpaid_invoices.aggregate(
                total=Sum("amount_remaining")
            )["total"] or 0

            context["today_collected"] = today_collected
            context["today_invoices_count"] = invoices_today.count()
            context["today_patients_count"] = today_patients_count
            context["total_unpaid_remaining"] = total_unpaid_remaining
            context["unpaid_invoices"] = unpaid_invoices
            context["unpaid_invoices_count"] = unpaid_invoices.count()

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
