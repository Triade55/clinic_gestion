# 🩺 Clinique SantéPlus — Documentation de l'API REST pour le Frontend

Ce document est le guide complet à destination de l'équipe **Frontend** (Web React/Vue/Angular, Mobile Flutter/React Native, etc.) pour interagir avec le backend de la clinique.

---

## 🌐 1. Informations Générales & Environnement

- **URL de base en développement** : `http://localhost:8000`
- **Format d'échange** : `application/json` (requêtes et réponses)
- **CORS** : Activé par défaut (`CORS_ALLOW_ALL_ORIGINS = True`, `credentials: true` supporté).
- **Fuseau horaire serveur** : `Africa/Abidjan` (UTC+0)

---

## 🔐 2. Authentification & Sécurité

L'API est séparée en deux zones :

1. **Zone Publique (Patients)** : Aucun en-tête d'authentification requis. Les patients interagissent directement avec leur numéro de réservation (`RES-XXXX`) et leur numéro de téléphone pour sécuriser leurs actions (consultation, report, annulation).
2. **Zone Protégée (Personnel Médical & Administratif)** : Requiert un token JWT transmis dans l'en-tête HTTP :
   ```http
   Authorization: Bearer <access_token>
   ```

---

## 🧭 3. Cycle de Vie d'un Rendez-vous & Statuts

Chaque rendez-vous traverse les statuts suivants :

| Statut Technique | Libellé Affiché | Rôle Responsable | Action Déclenchante |
| :--- | :--- | :--- | :--- |
| `EN_ATTENTE` | *En attente de confirmation* | Patient | Réservation effectuée en ligne |
| `CONFIRME` | *Confirmé* | Secrétaire | Validation par le secrétariat |
| `EN_SALLE_D_ATTENTE` | *En salle d'attente* | Secrétaire | Arrivée du patient au guichet physique (IPP `PAT-` généré si nouveau + facture émise) |
| `EN_CONSULTATION` | *En consultation* | Médecin | Le médecin appelle le patient et démarre |
| `TERMINE` | *Terminé* | Médecin | Consultation clôturée |
| `ANNULE` | *Annulé* | **Patient uniquement** | Le patient annule son rendez-vous |
| `ABSENT` | *Absent / Non honoré* | Système / Staff | Le patient ne s'est pas présenté |

---

## 📄 4. Références & Identifiants Patients

- **`booking_reference` (`RES-YYYYMM-XXXX`)** : Numéro de réservation temporaire remis immédiatement au patient lors de sa réservation en ligne.
- **`patient_number` (`PAT-YYYY-XXXX`)** : Numéro Unique Permanent du Patient (IPP). Attribué définitivement dès que le patient se présente au guichet d'accueil et règle sa consultation.

---

## 📑 5. Catalogue des Endpoints

### 🟢 A. ESPACE PUBLIC PATIENT (Sans Token)

---

#### 1. Lister les spécialités médicales
- **Méthode** : `GET`
- **Endpoint** : `/api/public/specialties/`
- **Description** : Renvoie la liste de toutes les spécialités médicales actives ainsi que le tarif de la consultation en Francs CFA.
- **Exemple de Réponse (`200 OK`)** :
  ```json
  [
    {
      "id": 1,
      "name": "Médecine Générale",
      "price": "5000",
      "is_active": true
    },
    {
      "id": 2,
      "name": "Pédiatrie",
      "price": "7500",
      "is_active": true
    },
    {
      "id": 4,
      "name": "Cardiologie",
      "price": "15000",
      "is_active": true
    }
  ]
  ```

---

#### 2. Obtenir les créneaux disponibles
- **Méthode** : `GET`
- **Endpoint** : `/api/public/slots/`
- **Query Parameters** :
  - `specialty_id` *(requis, int)* : ID de la spécialité
  - `date` *(requis, string)* : Date souhaitée au format `YYYY-MM-DD`
- **Exemple d'Appel** :
  `GET /api/public/slots/?specialty_id=1&date=2026-10-22`
- **Description** : Calcule en temps réel les créneaux disponibles en fonction des plannings des praticiens et déduit les créneaux déjà réservés.
- **Exemple de Réponse (`200 OK`)** :
  ```json
  {
    "date": "2026-10-22",
    "specialty_id": 1,
    "total_slots": 16,
    "slots": [
      {
        "time": "08:00",
        "available": true,
        "available_doctors_count": 1
      },
      {
        "time": "08:30",
        "available": true,
        "available_doctors_count": 1
      },
      {
        "time": "09:00",
        "available": false,
        "available_doctors_count": 0
      }
    ]
  }
  ```

---

#### 3. Réserver un rendez-vous en ligne
- **Méthode** : `POST`
- **Endpoint** : `/api/public/appointments/`
- **Description** : Permet à un patient (nouveau ou déjà connu) de prendre rendez-vous. Génère un reçu avec le numéro `RES-YYYYMM-XXXX`.
- **Corps de la requête (`JSON`)** :
  ```json
  {
    "first_name": "Koffi",
    "last_name": "Assamoi",
    "phone_number": "0708091011",
    "email": "koffi@test.ci",
    "specialty_id": 1,
    "appointment_date": "2026-10-22",
    "appointment_time": "08:30",
    "reason": "Maux de gorge et fièvre persistante",
    "patient_number": ""
  }
  ```
  *(Remarque : Le champ `patient_number` est optionnel. Si le patient a déjà un numéro de dossier `PAT-2026-0001`, il peut l'indiquer).*
- **Exemple de Réponse (`201 Created`)** :
  ```json
  {
    "message": "Votre demande de rendez-vous a été enregistrée avec succès.",
    "booking_reference": "RES-202610-0002",
    "appointment": {
      "id": 2,
      "booking_reference": "RES-202610-0002",
      "first_name": "Koffi",
      "last_name": "Assamoi",
      "full_name": "ASSAMOI Koffi",
      "phone_number": "0708091011",
      "email": "koffi@test.ci",
      "specialty": 1,
      "specialty_name": "Médecine Générale",
      "specialty_price": "5000",
      "doctor": 2,
      "doctor_name": "Dr Alexandre Martin",
      "patient": null,
      "patient_number": null,
      "is_new_patient": true,
      "appointment_date": "2026-10-22",
      "appointment_time": "08:30:00",
      "reason": "Maux de gorge et fièvre persistante",
      "status": "EN_ATTENTE",
      "status_label": "En attente de confirmation",
      "invoice": null,
      "invoice_number": null,
      "rescheduled_count": 0,
      "created_at": "2026-10-20T15:20:00Z"
    }
  }
  ```

---

#### 4. Consulter son rendez-vous (Suivi patient)
- **Méthode** : `POST`
- **Endpoint** : `/api/public/appointments/lookup/`
- **Description** : Permet au patient de retrouver ses rendez-vous pour voir leur état d'avancement.
- **Corps de la requête (`JSON`)** :
  ```json
  {
    "reference": "RES-202610-0002",
    "phone_number": "0708091011"
  }
  ```
- **Exemple de Réponse (`200 OK`)** :
  ```json
  [
    {
      "id": 2,
      "booking_reference": "RES-202610-0002",
      "full_name": "ASSAMOI Koffi",
      "specialty_name": "Médecine Générale",
      "appointment_date": "2026-10-22",
      "appointment_time": "08:30:00",
      "status": "CONFIRME",
      "status_label": "Confirmé"
    }
  ]
  ```

---

#### 5. Reporter son rendez-vous (Par le patient)
- **Méthode** : `PATCH`
- **Endpoint** : `/api/public/appointments/reschedule/`
- **Description** : Permet au patient de changer la date ou l'heure de son rendez-vous.
- **Corps de la requête (`JSON`)** :
  ```json
  {
    "reference": "RES-202610-0002",
    "phone_number": "0708091011",
    "new_date": "2026-10-23",
    "new_time": "10:00"
  }
  ```
- **Exemple de Réponse (`200 OK`)** :
  ```json
  {
    "message": "Rendez-vous reporté avec succès.",
    "appointment": {
      "id": 2,
      "booking_reference": "RES-202610-0002",
      "appointment_date": "2026-10-23",
      "appointment_time": "10:00:00",
      "rescheduled_count": 1
    }
  }
  ```

---

#### 6. Annuler son rendez-vous (Patient uniquement)
- **Méthode** : `POST`
- **Endpoint** : `/api/public/appointments/cancel/`
- **Description** : Permet au patient d'annuler son rendez-vous. *(Conformément aux règles métier de la clinique, le patient est le seul habilité à annuler ; le personnel interne a le droit de reporter uniquement).*
- **Corps de la requête (`JSON`)** :
  ```json
  {
    "reference": "RES-202610-0002",
    "phone_number": "0708091011",
    "reason": "Contrainte professionnelle de dernière minute"
  }
  ```
- **Exemple de Réponse (`200 OK`)** :
  ```json
  {
    "message": "Rendez-vous annulé avec succès.",
    "appointment": {
      "id": 2,
      "status": "ANNULE",
      "status_label": "Annulé",
      "cancelled_by": "PATIENT",
      "cancellation_reason": "Contrainte professionnelle de dernière minute"
    }
  }
  ```

---

### 🔑 B. AUTHENTIFICATION JWT (Personnel Clinique)

---

#### 1. Se connecter et obtenir le Token JWT
- **Méthode** : `POST`
- **Endpoint** : `/api/auth/token/`
- **Corps de la requête (`JSON`)** :
  ```json
  {
    "email": "sec.julie@clinique.fr",
    "password": "SecretaryPass123!"
  }
  ```
- **Exemple de Réponse (`200 OK`)** :
  ```json
  {
    "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
  ```

#### 2. Rafraîchir le Token JWT expiré
- **Méthode** : `POST`
- **Endpoint** : `/api/auth/token/refresh/`
- **Corps de la requête (`JSON`)** :
  ```json
  {
    "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
  ```
- **Exemple de Réponse (`200 OK`)** :
  ```json
  {
    "access": "nouvel_access_token_ici..."
  }
  ```

---

### 🔵 C. ESPACE PERSONNEL CLINIQUE (Protégé via Bearer Token)

> ⚠️ Toutes les requêtes ci-dessous exigent l'en-tête :  
> `Authorization: Bearer <votre_access_token>`

---

#### 1. Liste & Recherche de Rendez-vous
- **Méthode** : `GET`
- **Endpoint** : `/api/appointments/`
- **Rôles autorisés** : Secrétaire, Médecin, Infirmier, Administrateur
- **Filtres optionnels (Query params)** :
  - `?date=YYYY-MM-DD` : Filtrer par date exacte
  - `?status=EN_ATTENTE|CONFIRME|EN_SALLE_D_ATTENTE|EN_CONSULTATION|TERMINE|ANNULE|ABSENT`
  - `?specialty_id=1` : Filtrer par spécialité
  - `?doctor_id=2` : Filtrer par médecin assigné
  - `?search=Assamoi` : Recherche par nom, prénom, téléphone, référence `RES-` ou numéro `PAT-`
- **Exemple de Réponse (`200 OK`)** :
  ```json
  {
    "count": 1,
    "next": null,
    "previous": null,
    "results": [
      {
        "id": 2,
        "booking_reference": "RES-202610-0002",
        "full_name": "ASSAMOI Koffi",
        "phone_number": "0708091011",
        "specialty_name": "Médecine Générale",
        "doctor_name": "Dr Alexandre Martin",
        "appointment_date": "2026-10-22",
        "appointment_time": "08:30:00",
        "status": "EN_ATTENTE",
        "status_label": "En attente de confirmation",
        "is_new_patient": true
      }
    ]
  }
  ```

---

#### 2. Détail d'un Rendez-vous
- **Méthode** : `GET`
- **Endpoint** : `/api/appointments/{id}/`
- **Rôles autorisés** : Tout le personnel médical connecté

---

#### 3. Confirmer un Rendez-vous en ligne
- **Méthode** : `PATCH`
- **Endpoint** : `/api/appointments/{id}/confirm/`
- **Rôles autorisés** : Secrétaire médicale, Administrateur
- **Description** : Valide le RDV (`EN_ATTENTE` $\rightarrow$ `CONFIRME`).
- **Corps de la requête** : Aucun (ou `{}`)
- **Exemple de Réponse (`200 OK`)** :
  ```json
  {
    "message": "Rendez-vous confirmé avec succès.",
    "appointment": {
      "id": 2,
      "status": "CONFIRME",
      "status_label": "Confirmé"
    }
  }
  ```

---

#### 4. Enregistrement au guichet physique (Check-in Patient)
- **Méthode** : `PATCH`
- **Endpoint** : `/api/appointments/{id}/checkin/`
- **Rôles autorisés** : Secrétaire médicale, Administrateur
- **Description** :
  1. Si le patient n'avait pas encore d'IPP officiel, génère automatiquement son numéro de dossier `PAT-YYYY-XXXX`.
  2. Émet automatiquement la facture de consultation associée (`FAC-YYYYMM-XXXX`) avec statut `UNPAID` (en attente de règlement au guichet).
  3. Fait passer le statut à `EN_SALLE_D_ATTENTE`.
- **Exemple de Réponse (`200 OK`)** :
  ```json
  {
    "message": "Patient enregistré avec succès et orienté vers la salle d'attente.",
    "patient_number": "PAT-2026-0004",
    "invoice_number": "FAC-202610-0002",
    "appointment": {
      "id": 2,
      "patient": 4,
      "patient_number": "PAT-2026-0004",
      "invoice": 2,
      "invoice_number": "FAC-202610-0002",
      "status": "EN_SALLE_D_ATTENTE",
      "status_label": "En salle d'attente"
    }
  }
  ```

---

#### 5. Démarrer la consultation (Par le médecin)
- **Méthode** : `PATCH`
- **Endpoint** : `/api/appointments/{id}/start/`
- **Rôles autorisés** : Médecin (`DOCTOR`), Administrateur
- **Description** : Assigne automatiquement le praticien connecté et passe le statut à `EN_CONSULTATION`.
- **Exemple de Réponse (`200 OK`)** :
  ```json
  {
    "message": "Consultation démarrée.",
    "appointment": {
      "id": 2,
      "status": "EN_CONSULTATION",
      "status_label": "En consultation"
    }
  }
  ```

---

#### 6. Terminer la consultation (Par le médecin)
- **Méthode** : `PATCH`
- **Endpoint** : `/api/appointments/{id}/finish/`
- **Rôles autorisés** : Médecin (`DOCTOR`), Administrateur
- **Description** : Clôture la consultation (`EN_CONSULTATION` $\rightarrow$ `TERMINE`).
- **Exemple de Réponse (`200 OK`)** :
  ```json
  {
    "message": "Consultation clôturée avec succès.",
    "appointment": {
      "id": 2,
      "status": "TERMINE",
      "status_label": "Terminé"
    }
  }
  ```

---

#### 7. Reporter un Rendez-vous (Par le personnel médical)
- **Méthode** : `PATCH`
- **Endpoint** : `/api/appointments/{id}/reschedule/`
- **Rôles autorisés** : Secrétaire, Médecin, Administrateur
- **Corps de la requête (`JSON`)** :
  ```json
  {
    "new_date": "2026-10-25",
    "new_time": "14:00",
    "doctor_id": null
  }
  ```
  *(Remarque : `doctor_id` est optionnel si vous souhaitez réassigner un médecin précis).*

---

#### 8. Gestion des Disponibilités des Médecins
- **`GET /api/doctor/availabilities/`** : Récupérer ses plages horaires hebdomadaires.
- **`POST /api/doctor/availabilities/`** : Créer une plage horaire récurrente.
  ```json
  {
    "specialty": 1,
    "day_of_week": 0,
    "start_time": "08:00:00",
    "end_time": "16:00:00",
    "slot_duration_minutes": 30,
    "is_active": true
  }
  ```
  *(Jours de la semaine : 0=Lundi, 1=Mardi, 2=Mercredi, 3=Jeudi, 4=Vendredi, 5=Samedi, 6=Dimanche).*
- **`PUT /api/doctor/availabilities/{id}/`** : Mettre à jour une disponibilité.
- **`DELETE /api/doctor/availabilities/{id}/`** : Supprimer une disponibilité.

---

## 🛠️ 6. Exemples d'Intégration Frontend (JavaScript / Axios / Fetch)

### Exemple A : Récupérer les créneaux disponibles (Fetch)
```javascript
async function getAvailableSlots(specialtyId, date) {
  const response = await fetch(
    `http://localhost:8000/api/public/slots/?specialty_id=${specialtyId}&date=${date}`
  );
  if (!response.ok) {
    throw new Error("Erreur lors de la récupération des créneaux");
  }
  const data = await response.json();
  return data.slots; // [{ time: "08:00", available: true }, ...]
}
```

### Exemple B : Réserver en ligne (Axios)
```javascript
import axios from "axios";

async function bookAppointment(bookingData) {
  try {
    const response = await axios.post(
      "http://localhost:8000/api/public/appointments/",
      bookingData
    );
    console.log("Code de réservation:", response.data.booking_reference);
    return response.data;
  } catch (error) {
    console.error("Erreur de réservation:", error.response?.data);
    throw error;
  }
}
```

### Exemple C : Appel avec Token JWT (Espace Interne)
```javascript
import axios from "axios";

const api = axios.create({
  baseURL: "http://localhost:8000/api",
});

// Intercepteur pour injecter le Token Bearer
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Confirmer un rendez-vous (Secrétaire)
export async function confirmAppointment(appointmentId) {
  const response = await api.patch(`/appointments/${appointmentId}/confirm/`);
  return response.data;
}

// Enregistrement au guichet (Secrétaire)
export async function checkinPatient(appointmentId) {
  const response = await api.patch(`/appointments/${appointmentId}/checkin/`);
  return response.data;
}
```

---

## 🧪 7. Comptes de Test pour l'Équipe Frontend

| Rôle | Adresse Email | Mot de passe | Usage frontend |
| :--- | :--- | :--- | :--- |
| **Secrétaire / Caisse** | `sec.julie@clinique.fr` | `SecretaryPass123!` | Test confirmation, check-in, report |
| **Médecin** | `dr.martin@clinique.fr` | `DoctorPass123!` | Test démarrage consultation, clôture, disponibilités |
| **Administrateur** | `admin@clinique.fr` | `AdminPass123!` | Accès complet tous droits |
