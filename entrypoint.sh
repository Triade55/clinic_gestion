#!/bin/sh
set -e

if [ -n "$POSTGRES_DB" ]; then
    echo "En attente de la base de données PostgreSQL (${POSTGRES_HOST:-db}:${POSTGRES_PORT:-5432})..."
    python << 'EOF'
import os
import socket
import time

host = os.environ.get("POSTGRES_HOST", "db")
port = int(os.environ.get("POSTGRES_PORT", "5432"))
start_time = time.time()
while True:
    try:
        with socket.create_connection((host, port), timeout=2):
            print("PostgreSQL est prêt !")
            break
    except (OSError, socket.error):
        if time.time() - start_time > 60:
            raise TimeoutError("Délai d'attente dépassé pour la connexion à PostgreSQL")
        time.sleep(1)
EOF
fi

echo "Application des migrations Django..."
python manage.py migrate --noinput

echo "Collecte des fichiers statiques..."
python manage.py collectstatic --noinput

if [ "$AUTO_SEED" = "1" ] || [ "$AUTO_SEED" = "true" ]; then
    echo "Initialisation des données de démonstration..."
    python manage.py seed_users || true
    python manage.py seed_billing || true
    python manage.py seed_appointments || true
fi

echo "Démarrage du serveur d'application..."
exec "$@"
