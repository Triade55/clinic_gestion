import json
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import DetailView, ListView

from .forms import EncaissementForm
from .models import Invoice, Patient, Specialty


class EncaissementCreateView(LoginRequiredMixin, View):
    """
    Vue principale d'encaissement et d'admission à l'accueil.
    La secrétaire sélectionne/crée le patient, choisit la consultation,
    saisit le montant reçu, et le système calcule le montant rendu
    avant d'éditer la facture imprimable.
    """
    template_name = "billing/encaissement_form.html"

    def get(self, request):
        form = EncaissementForm()
        specialties = Specialty.objects.filter(is_active=True)
        # Préparer un dictionnaire id -> prix pour le calcul dynamique JS en direct
        specialty_prices = {s.id: int(s.price) for s in specialties}

        context = {
            "form": form,
            "specialties": specialties,
            "specialty_prices_json": json.dumps(specialty_prices),
            "recent_invoices": Invoice.objects.select_related("patient", "specialty").order_by("-created_at")[:5],
        }
        return render(request, self.template_name, context)

    def post(self, request):
        form = EncaissementForm(request.POST)
        specialties = Specialty.objects.filter(is_active=True)
        specialty_prices = {s.id: int(s.price) for s in specialties}

        if form.is_valid():
            with transaction.atomic():
                patient_mode = form.cleaned_data["patient_mode"]
                specialty = form.cleaned_data["specialty"]
                amount_received = form.cleaned_data["amount_received"]

                if patient_mode == "EXISTING":
                    patient = form.cleaned_data["patient_obj"]
                else:
                    patient = Patient.objects.create(
                        patient_number=Patient.generate_patient_number(),
                        first_name=form.cleaned_data["first_name"].strip(),
                        last_name=form.cleaned_data["last_name"].strip(),
                        phone_number=form.cleaned_data.get("phone_number", "").strip(),
                    )

                # Création de la facture / encaissement (save() calcule la monnaie ou le reste à payer)
                invoice = Invoice.objects.create(
                    patient=patient,
                    specialty=specialty,
                    consultation_fee=specialty.price,
                    amount_received=amount_received,
                    created_by=request.user,
                )

            if invoice.amount_remaining > 0:
                msg = (
                    f"Paiement partiel enregistré ! Tarif : {int(invoice.consultation_fee):,} FCFA | "
                    f"Reçu : {int(invoice.amount_received):,} FCFA | "
                    f"Reste à payer : {int(invoice.amount_remaining):,} FCFA."
                ).replace(",", " ")
            elif invoice.amount_change > 0:
                msg = (
                    f"Encaissement validé ! Tarif : {int(invoice.consultation_fee):,} FCFA | "
                    f"Reçu : {int(invoice.amount_received):,} FCFA | "
                    f"Monnaie à rendre : {int(invoice.amount_change):,} FCFA."
                ).replace(",", " ")
            else:
                msg = (
                    f"Encaissement validé (compte exact) ! "
                    f"Tarif : {int(invoice.consultation_fee):,} FCFA réglé en totalité."
                ).replace(",", " ")

            messages.success(request, _(msg))
            return redirect("billing:invoice_detail", pk=invoice.pk)

        context = {
            "form": form,
            "specialties": specialties,
            "specialty_prices_json": json.dumps(specialty_prices),
            "recent_invoices": Invoice.objects.select_related("patient", "specialty").order_by("-created_at")[:5],
        }
        return render(request, self.template_name, context)


class InvoiceDetailView(LoginRequiredMixin, DetailView):
    """
    Affiche la facture / reçu officiel prêt pour l'impression (window.print()).
    Contient le numéro de patient unique, la spécialité, les montants et le rendu.
    """
    model = Invoice
    template_name = "billing/invoice_detail.html"
    context_object_name = "invoice"


class InvoiceListView(LoginRequiredMixin, ListView):
    """
    Historique des encaissements et factures de la clinique.
    Permet de réimprimer n'importe quel reçu émis.
    """
    model = Invoice
    template_name = "billing/invoice_list.html"
    context_object_name = "invoices"
    paginate_by = 20

    def get_queryset(self):
        qs = Invoice.objects.select_related("patient", "specialty", "created_by").order_by("-created_at")
        search = self.request.GET.get("q", "").strip()
        if search:
            qs = qs.filter(
                patient__patient_number__icontains=search
            ) | qs.filter(
                patient__last_name__icontains=search
            ) | qs.filter(
                patient__first_name__icontains=search
            ) | qs.filter(
                invoice_number__icontains=search
            )
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_query"] = self.request.GET.get("q", "").strip()
        return context
