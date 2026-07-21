#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${1:-.}"

if [ ! -f "$ROOT/pyproject.toml" ]; then
  echo "Uruchom z katalogu slr-platform lub podaj ścieżkę."
  exit 1
fi

cd "$ROOT"

echo "===> Tworzenie nowej struktury"

mkdir -p  app/domain  app/providers  app/services  app/storage  app/config

touch  app/domain/__init__.py  app/providers/__init__.py  app/services/__init__.py  app/storage/__init__.py  app/config/__init__.py

echo "===> Przenoszenie modeli domenowych"

if [ -f app/core/models.py ]; then
    git mv app/core/models.py app/domain/models.py 2>/dev/null || mv app/core/models.py app/domain/models.py
fi

echo "===> Przenoszenie providerów"

mkdir -p app/providers/search

if [ -d app/modules/search/providers ]; then
    git mv app/modules/search/providers/* app/providers/search/ 2>/dev/null || mv app/modules/search/providers/* app/providers/search/
    rmdir app/modules/search/providers 2>/dev/null || true
fi

echo
echo "UWAGA:"
echo "Importy NIE zostały jeszcze zmienione."
echo "To będzie etap 4."
echo
echo "Nowa struktura:"
find app -maxdepth 2 -type d | sort

echo
echo "Następnie wykonaj:"
echo "git status"
echo "pytest"
echo "git add -A"
echo "git commit -m 'refactor: introduce domain and provider layers'"
