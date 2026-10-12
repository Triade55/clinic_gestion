import json
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import DetailView, ListView

from .forms import EncaissementForm, InvoicePaymentForm
from .models import Invoice, InvoicePayment, Patient, Specialty


class PatientSearchView(LoginRequiredMixin, View):
    """
    Recherche dynamique de patients en JSON pour l'autocomplétion en direct
    et la vérification d'identité immédiate lors de la saisie du numéro de patient.
    Supporte la recherche par numéro IPP, nom, prénom ou téléphone.
    """
    def get(self, request):
        query = request.GET.get("q", "").strip()
        exact_number = request.GET.get("patient_number", "").strip()

        if exact_number:
            patients = Patient.objects.filter(patient_number__iexact=exact_number)[:1]
        elif query:
            patients = Patient.objects.filter(
                Q(patient_number__icontains=query)
                | Q(last_name__icontains=query)
                | Q(first_name__icontains=query)
                | Q(phone_number__icontains=query)
            ).order_by("-created_at")[:10]
        else:
            patients = Patient.objects.none()

        results = []
        for p in patients:
            invoices = p.invoices.select_related("specialty").order_by("-created_at")
            last_invoice = invoices.first()
            results.append({
                "id": p.id,
                "patient_number": p.patient_number,
                "first_name": p.first_name,
                "last_name": p.last_name.upper(),
                "full_name": p.full_name,
                "phone_number": p.phone_number if p.phone_number else "Non renseigné",
                "created_at": p.created_at.strftime("%d/%m/%Y"),
                "invoices_count": invoices.count(),
                "last_visit": last_invoice.created_at.strftime("%d/%m/%Y à %H:%M") if last_invoice else None,
                "last_specialty": last_invoice.specialty.name if last_invoice else None,
            })

        return JsonResponse({"results": results})



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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["payments"] = self.object.payments.select_related("created_by").order_by("created_at")
        return context


class InvoiceListView(LoginRequiredMixin, ListView):
    """
    Historique des encaissements et factures de la clinique.
    Permet de réimprimer n'importe quel reçu émis et de filtrer par statut de paiement.
    """
    model = Invoice
    template_name = "billing/invoice_list.html"
    context_object_name = "invoices"
    paginate_by = 20

    def get_queryset(self):
        qs = Invoice.objects.select_related("patient", "specialty", "created_by").order_by("-created_at")
        status_filter = self.request.GET.get("status", "").strip()
        if status_filter == "unpaid":
            qs = qs.filter(amount_remaining__gt=0)
        elif status_filter == "paid":
            qs = qs.filter(amount_remaining=0)

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
        context["current_status"] = self.request.GET.get("status", "").strip()
        context["total_count"] = Invoice.objects.count()
        context["unpaid_count"] = Invoice.objects.filter(amount_remaining__gt=0).count()
        context["paid_count"] = Invoice.objects.filter(amount_remaining=0).count()
        return context


class InvoicePaymentCreateView(LoginRequiredMixin, View):
    """
    Permet à la secrétaire / caisse d'enregistrer un versement ou un solde
    sur une facture comportant un reliquat impayé.
    """
    template_name = "billing/payment_form.html"

    def get(self, request, pk):
        invoice = get_object_or_404(
            Invoice.objects.select_related("patient", "specialty"), pk=pk
        )
        if invoice.amount_remaining <= 0:
            messages.info(request, _("Cette facture est déjà intégralement soldée."))
            return redirect("billing:invoice_detail", pk=invoice.pk)

        form = InvoicePaymentForm(invoice=invoice)
        context = {
            "invoice": invoice,
            "form": form,
            "previous_payments": invoice.payments.select_related("created_by").order_by("created_at"),
        }
        return render(request, self.template_name, context)

    def post(self, request, pk):
        with transaction.atomic():
            invoice = get_object_or_404(
                Invoice.objects.select_for_update().select_related("patient", "specialty"), pk=pk
            )
            if invoice.amount_remaining <= 0:
                messages.info(request, _("Cette facture est déjà intégralement soldée."))
                return redirect("billing:invoice_detail", pk=invoice.pk)

            form = InvoicePaymentForm(request.POST, invoice=invoice)
            if form.is_valid():
                amount_paid = form.cleaned_data["amount_paid"]
                amount_received = form.cleaned_data.get("amount_received") or amount_paid
                amount_change = form.cleaned_data.get("amount_change", 0)
                payment_method = form.cleaned_data["payment_method"]
                note = form.cleaned_data.get("note", "").strip()

                payment = invoice.add_payment(
                    amount_paid=amount_paid,
                    amount_received=amount_received,
                    amount_change=amount_change,
                    payment_method=payment_method,
                    note=note,
                    created_by=request.user,
                )

                if invoice.amount_remaining == 0:
                    msg = (
                        f"Facture {invoice.invoice_number} intégralement soldée ! "
                        f"Versement de {int(amount_paid):,} FCFA enregistré (Reçu {payment.payment_number})."
                    ).replace(",", " ")
                else:
                    msg = (
                        f"Versement de {int(amount_paid):,} FCFA enregistré avec succès ! "
                        f"Nouveau reste à payer : {int(invoice.amount_remaining):,} FCFA (Reçu {payment.payment_number})."
                    ).replace(",", " ")

                messages.success(request, _(msg))
                return redirect("billing:payment_receipt", pk=payment.pk)

        context = {
            "invoice": invoice,
            "form": form,
            "previous_payments": invoice.payments.select_related("created_by").order_by("created_at"),
        }
        return render(request, self.template_name, context)


class PaymentReceiptView(LoginRequiredMixin, DetailView):
    """
    Affiche le reçu officiel d'un versement individuel prêt pour l'impression.
    """
    model = InvoicePayment
    template_name = "billing/payment_receipt.html"
    context_object_name = "payment"

    def get_queryset(self):
        return InvoicePayment.objects.select_related(
            "invoice", "invoice__patient", "invoice__specialty", "created_by"
        )
