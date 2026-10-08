#!/bin/sh
# Garde-fou du garde-fou : l'étape licences de audit.sh doit refuser chaque licence piégée
# ci-dessous, essayée sur un faux paquet installé le temps de l'essai, et accepter le témoin MIT.
# Sans ce test, remettre --partial-match sur la liste blanche passerait inaperçu.
set -u
cd "$(dirname "$0")/.."
SITE=$(.venv/bin/python -c "import sysconfig; print(sysconfig.get_paths()['purelib'])")
FAKE="$SITE/piege_licence-1.0.dist-info"
trap 'rm -rf "$FAKE"' EXIT
FAILED=0

check() {  # check <bloque|accepte> <métadonnées du faux paquet>
  mkdir -p "$FAKE"
  printf 'Metadata-Version: 2.4\nName: piege-licence\nVersion: 1.0\n%b' "$2" > "$FAKE/METADATA"
  : > "$FAKE/RECORD"
  if scripts/audit.sh --licences-only > /dev/null 2>&1; then got=accepte; else got=bloque; fi
  rm -rf "$FAKE"
  [ "$got" = "$1" ] || { echo "ÉCHEC : $(printf %b "$2" | tr "\n" " ")-> $got, attendu : $1"; FAILED=1; }
}

check accepte 'License-Expression: MIT\n'  # témoin : l'audit tourne et accepte une licence admise
check bloque 'License: Proprietary - Limited Use\n'  # « MIT » est une sous-chaîne de « liMITed »
check bloque 'License: Commercial, no redistribution (submit a request)\n'  # … et de « subMIT »
check bloque 'License-Expression: Apache-2.0 WITH Commons-Clause\n'  # « Apache » + clause non commerciale
check bloque 'License-Expression: Elastic-2.0\n'
check bloque 'License-Expression: CC-BY-NC-4.0\n'
check bloque 'License-Expression: GPL-3.0-or-later OR MIT\n'
check bloque 'License-Expression: LGPL-3.0-only\n'
check bloque 'Classifier: License :: OSI Approved :: MIT License\nClassifier: License :: Other/Proprietary License\n'
check bloque 'License-Expression: MIT-0\n'  # permissive, mais jamais vue : revue humaine d'abord

[ $FAILED -eq 0 ] && echo "OK : l'audit des licences bloque toutes les licences piégées"
exit $FAILED
