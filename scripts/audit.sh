#!/bin/sh
# Contrôle exigé par la direction : aucun composant externe sans vérification de sa licence
# et de sa fraîcheur. À lancer avant tout ajout/mise à jour de dépendance (et en CI).
#   bloquant   : licence hors liste blanche ou interdite, vulnérabilité connue
#   informatif : paquets en retard sur leur dernière version stable
#   produit    : sbom.cdx.json (CycloneDX) des seules dépendances livrées avec le produit
set -eu
cd "$(dirname "$0")/.."
VENV=.venv/bin
PY=${PYTHON:-python3.13}
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

echo "== 1/4 Licences de tout l'environnement (directes + transitives, runtime + dev)"
# Notre propre paquet (LicenseRef-Proprietary) est exclu : pip-licenses le lit comme UNKNOWN.
# a) Liste BLANCHE, en correspondance EXACTE : une licence absente, UNKNOWN ou jamais vue bloque
#    jusqu'à vérification humaine, qui l'ajoute ici. Jamais --partial-match pour la liste blanche :
#    « MIT » y est cherché comme sous-chaîne et accepte « Limited Use », « submit », « Permits »…
#    MPL-2.0 (copyleft faible, par fichier, outillage de dev uniquement) est tolérée.
ALLOWED="MIT;MIT License;Apache-2.0;Apache Software License;Apache-2.0 OR BSD-2-Clause"
ALLOWED="$ALLOWED;BSD-2-Clause;BSD-3-Clause;BSD License;PSF-2.0;Python Software Foundation License"
ALLOWED="$ALLOWED;Mozilla Public License 2.0 (MPL 2.0)"
"$VENV/pip-licenses" --with-system --ignore-packages reveil-musical --allow-only "$ALLOWED" > /dev/null
# b) Liste NOIRE, en sous-chaîne : rattrape un paquet qui déclare à la fois une licence admise et
#    une licence interdite (la liste blanche se contente d'une seule admise). « GPL » couvre AGPL et
#    LGPL, même dans « X OR GPL » ; s'y ajoutent les licences « source disponible » non commerciales.
DENIED="GPL;SSPL;EUPL;Commons Clause;Commons-Clause;Proprietary;Non-Commercial;NonCommercial"
DENIED="$DENIED;BUSL;Business Source;Elastic License"
"$VENV/pip-licenses" --with-system --ignore-packages reveil-musical --partial-match --fail-on "$DENIED" > /dev/null
echo "OK : uniquement des licences permissives (ou MPL-2.0 justifiée)"
[ "${1:-}" = "--licences-only" ] && exit 0  # utilisé par scripts/audit_selftest.sh

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
