#!/bin/sh
# Contrôle exigé par la direction : aucun composant externe sans vérification de sa licence
# et de sa fraîcheur. À lancer avant tout ajout/mise à jour de dépendance (et en CI).
#   bloquant   : licence copyleft forte, vulnérabilité connue
#   informatif : paquets en retard sur leur dernière version stable
#   produit    : sbom.cdx.json (CycloneDX) des seules dépendances livrées avec le produit
set -eu
cd "$(dirname "$0")/.."
VENV=.venv/bin
PY=${PYTHON:-python3.13}
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

echo "== 1/4 Licences de tout l'environnement (directes + transitives, runtime + dev)"
# Liste BLANCHE : une licence absente, UNKNOWN ou nouvelle bloque jusqu'à vérification humaine.
# La liste noire reste en garde-fou : « GPL » (--partial-match) couvre aussi AGPL et LGPL, même
# glissé dans une expression « X OR GPL ». MPL-2.0 (copyleft faible, par fichier) est toléré.
# Notre propre paquet (LicenseRef-Proprietary) est exclu : pip-licenses le lit comme UNKNOWN.
"$VENV/pip-licenses" --with-system --partial-match --ignore-packages reveil-musical \
  --allow-only "MIT;BSD;Apache;Python Software Foundation;PSF-2.0;Mozilla Public License 2.0" \
  --fail-on "GPL;SSPL;EUPL" > /dev/null
echo "OK : uniquement des licences permissives (ou MPL-2.0 justifiée)"

echo "== 2/4 Vulnérabilités connues (versions exactes du fichier de verrouillage)"
"$VENV/pip-audit" --strict --no-deps --disable-pip -r requirements-dev.lock

echo "== 3/4 Fraîcheur (informatif)"
OUTDATED=$("$VENV/pip" list --outdated --exclude-editable)
echo "${OUTDATED:-OK : tous les paquets sont à leur dernière version stable}"

echo "== 4/4 SBOM CycloneDX -> sbom.cdx.json"
# Outil jetable, hors du projet : cyclonedx-bom tirerait 21 paquets de plus dans l'environnement.
"$PY" -m venv "$WORK/tools" && "$WORK/tools/bin/pip" install -q cyclonedx-bom==7.5.0
# Environnement minimal = exactement ce qui est livré (dépendances runtime, sans l'outillage de dev).
"$PY" -m venv --without-pip "$WORK/runtime" && "$VENV/pip" --python "$WORK/runtime/bin/python" install -q .
"$WORK/tools/bin/cyclonedx-py" environment --pyproject pyproject.toml --of JSON -o sbom.cdx.json "$WORK/runtime/bin/python"
echo "OK"
