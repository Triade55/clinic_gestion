from rest_framework import permissions
from accounts.models import User


class IsClinicStaff(permissions.BasePermission):
    """
    Vérifie que l'utilisateur est un membre du personnel de la clinique.
    """
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.role in [User.Role.ADMIN, User.Role.SECRETARY, User.Role.DOCTOR, User.Role.NURSE]
                 or request.user.is_superuser)
        )


class IsDoctorUser(permissions.BasePermission):
    """
    Vérifie que l'utilisateur connecté est un médecin ou administrateur.
    """
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.role == User.Role.DOCTOR or request.user.is_superuser or request.user.role == User.Role.ADMIN)
        )


class IsSecretaryOrAdmin(permissions.BasePermission):
    """
    Vérifie que l'utilisateur connecté est une secrétaire ou un administrateur.
    """
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.role in [User.Role.SECRETARY, User.Role.ADMIN] or request.user.is_superuser)
        )
