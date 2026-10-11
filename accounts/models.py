from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class CustomUserManager(BaseUserManager):
    """
    Gestionnaire personnalisé pour créer des utilisateurs avec email
    au lieu de nom d'utilisateur (username).
    """

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError(_("L'adresse email est obligatoire."))
        email = self.normalize_email(email)
        extra_fields.setdefault("is_active", True)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.ADMIN)

        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Le superutilisateur doit avoir is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Le superutilisateur doit avoir is_superuser=True."))

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    Modèle utilisateur personnalisé pour le personnel de la clinique.
    La connexion s'effectue via l'adresse email.
    """

    class Role(models.TextChoices):
        ADMIN = "ADMIN", _("Administrateur / Direction")
        DOCTOR = "DOCTOR", _("Médecin / Praticien")
        NURSE = "NURSE", _("Infirmier / Personnel soignant")
        SECRETARY = "SECRETARY", _("Secrétaire médicale / Réception")

    username = None
    email = models.EmailField(
        _("Adresse email"),
        unique=True,
        max_length=255,
        error_messages={
            "unique": _("Un compte avec cette adresse email existe déjà."),
        },
    )
    role = models.CharField(
        _("Rôle dans la clinique"),
        max_length=20,
        choices=Role.choices,
        default=Role.SECRETARY,
    )
    phone_number = models.CharField(
        _("Numéro de téléphone"),
        max_length=30,
        blank=True,
    )
    specialty = models.CharField(
        _("Spécialité médicale"),
        max_length=120,
        blank=True,
        help_text=_("Optionnel : pour les praticiens (ex. Médecine générale, Cardiologie, Pédiatrie)"),
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = CustomUserManager()

    class Meta:
        verbose_name = _("Utilisateur")
        verbose_name_plural = _("Utilisateurs")
        ordering = ["last_name", "first_name", "email"]

    def __str__(self):
        full_name = self.get_full_name()
        if full_name.strip():
            return f"{full_name} ({self.get_role_display()})"
        return f"{self.email} ({self.get_role_display()})"

    @property
    def is_admin_role(self):
        return self.role == self.Role.ADMIN or self.is_superuser

    @property
    def is_doctor(self):
        return self.role == self.Role.DOCTOR

    @property
    def is_nurse(self):
        return self.role == self.Role.NURSE

    @property
    def is_secretary(self):
        return self.role == self.Role.SECRETARY
