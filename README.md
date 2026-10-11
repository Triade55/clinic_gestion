# Clinique SantéPlus — Système Intégré de Gestion Médicale

Plateforme de gestion pour clinique médicale développée avec **Django** (rendu serveur sécurisé, formulaires natifs et contrôle d'accès RBAC).

---

## 🚀 Fonctionnalités Actuelles

### 1. Authentification & Rôles Professionnels (`accounts`)
- **Modèle Utilisateur Personnalisé (`CustomUser`)** connecté par **adresse email unique**.
- Rôles cliniques intégrés :
  - `ADMIN` : Direction & Administration générale.
  - `DOCTOR` : Médecin / Praticien référent.
  - `NURSE` : Personnel soignant / Infirmier.
  - `SECRETARY` : Secrétaire médicale / Caisse & Accueil.
- Décorateurs et Mixins de sécurité basés sur les rôles (`@role_required`, etc.).
- Gestion des mots de passe (modification, réinitialisation sécurisée).

### 2. Accueil, Caisse & Encaissement des Consultations (`billing`)
- **Numéro Unique Permanent de Patient (IPP)** : format `PAT-YYYY-XXXX` généré automatiquement pour chaque patient et conservé lors de chaque passage.
- **Orientation & Prise en charge** :
  - Prise en charge d'un **Nouveau Patient** (Nom, Prénom, Téléphone) ou recherche d'un **Patient Existant** par son numéro de dossier.
  - Sélection de la spécialité médicale avec tarif en **FCFA**.
- **Gestion des Règlements** :
  - Calcul et affichage en temps réel de la **monnaie à rendre** ou du **reste à payer** (paiement partiel / acompte).
  - Statuts gérés : *Soldé / Réglé*, *Paiement partiel / Acompte*, *Non réglé*.
- **Facture & Reçu Imprimable** :
  - Émission de reçu instantané avec numéro de facture (`FAC-YYYYMM-XXXX`) et numéro de patient mis en avant.
  - Bouton d'impression optimisé (`window.print()`).
- **Historique & Recherche** : Consultation et réimpression des reçus émis.

---

## 🛠️ Installation & Lancement

### Prérequis
- Python 3.12+
- Django 6.1+

### Installation
```bash
# Cloner le dépôt
git clone <url_du_depot>
cd clinic_gestion

# Activer l'environnement virtuel
source .venv/bin/activate

# Installer les dépendances
pip install django

# Appliquer les migrations
python manage.py migrate
```

### Initialiser les Données de Démonstration (Seed)
```bash
# 1. Créer les comptes professionnels de démonstration
python manage.py seed_users

# 2. Créer les spécialités, tarifs FCFA et patients de test
python manage.py seed_billing
```

### Lancer le Serveur
```bash
python manage.py runserver
```
L'application est accessible sur : `http://127.0.0.1:8000/`.

---

## 🔑 Comptes de Démonstration

| Rôle | Adresse Email | Mot de passe |
| :--- | :--- | :--- |
| **Administrateur** | `admin@clinique.fr` | `AdminPass123!` |
| **Médecin** | `dr.martin@clinique.fr` | `DoctorPass123!` |
| **Infirmière** | `inf.sophie@clinique.fr` | `NursePass123!` |
| **Secrétaire / Caisse** | `sec.julie@clinique.fr` | `SecretaryPass123!` |

---

## 🧪 Tests Automatisés

Pour lancer l'ensemble de la suite de tests (17 tests) :
```bash
python manage.py test accounts billing
```
