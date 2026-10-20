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

### Lancement Rapide avec Docker Compose 🐳 (Recommandé)

Le projet intègre une configuration Docker Compose de production avec serveur d'application **Gunicorn**, serveur de fichiers statiques optimisé **WhiteNoise**, base de données relationnelle **PostgreSQL 16**, et initialisation automatique :

```bash
# 1. Copier le fichier d'environnement (optionnel, valeurs par défaut incluses)
cp .env.example .env

# 2. Construire et démarrer les conteneurs (Django Web + PostgreSQL)
docker compose up -d --build

# 3. Consulter les journaux en direct
docker compose logs -f web
```
L'application est immédiatement accessible sur : **`http://localhost:8000/`**.

> 💡 Les migrations de schéma et les données de démonstration (`seed_users`, `seed_billing`) sont appliquées automatiquement au premier démarrage via `AUTO_SEED=1`.

---

### Installation Locale Traditionnelle (Alternative)

```bash
# Cloner le dépôt
git clone <url_du_depot>
cd clinic_gestion

# Activer l'environnement virtuel
source .venv/bin/activate

# Installer les dépendances
pip install -r requirements.txt

# Appliquer les migrations
python manage.py migrate

# Initialiser les données de démonstration (Seed)
python manage.py seed_users
python manage.py seed_billing

# Lancer le serveur de développement
python manage.py runserver
```
L'application est accessible sur : `http://127.0.0.1:8000/`.

---

### 3. Prise de Rendez-vous & API REST (`appointments`)
- **API REST & CORS** : Intégration de Django REST Framework, SimpleJWT (`Bearer`) et `django-cors-headers`.
- **Espace Public Patient (sans authentification)** :
  - Consultation des spécialités et tarifs (`/api/public/specialties/`).
  - Détection dynamique des créneaux horaires disponibles par médecin et spécialité (`/api/public/slots/`).
  - Prise de rendez-vous en ligne avec émission d'un reçu et code de réservation (`RES-YYYYMM-XXXX`).
  - Consultation, report et annulation (réservée exclusivement au patient via `RES-` / `PAT-` + téléphone).
- **Cycle de Vie & Traçabilité Clinique** :
  - `EN_ATTENTE` : Réservation en ligne.
  - `CONFIRME` : Validation par la secrétaire.
  - `EN_SALLE_D_ATTENTE` : Enregistrement au guichet (attribution de l'IPP officiel `PAT-YYYY-XXXX` si nouveau patient + création de la facture `Invoice`).
  - `EN_CONSULTATION` : Prise en charge par le médecin.
  - `TERMINE` : Clôture de la consultation par le praticien.
  - `ANNULE` / `ABSENT` : Annulation par le patient ou créneau dépassé.

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

Pour lancer l'ensemble de la suite de tests (30 tests) :
```bash
docker compose exec web python manage.py test
```

