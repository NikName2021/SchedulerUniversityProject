#!/bin/bash
echo "[deploy] starting"

if [ ! -f .env ]; then
  echo "[deploy] .env not found, creating from .env.example"
  python3 create_env.py
fi

if [ ! -f ./spa/.env]; then
  cp ./spa/.env.example ./spa/.env
fi

echo "[deploy] stopping existing containers"
docker compose down --remove-orphans

echo "[deploy] building and starting"
docker compose up -d --build

