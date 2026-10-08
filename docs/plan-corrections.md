# Plan de correction — revue du 2026-10-08

**Objectif** : combler les 16 écarts relevés par la revue (sujet du TP + supports J1/J2) sans casser l'architecture existante.
**Méthode** : TDD (test rouge → code minimal → vert), un commit par tâche, suite complète verte et couverture ≥ 90 % à chaque commit.
**Statut** : ✅ toutes les tâches réalisées, un commit par tâche (`git log`) ; suite par défaut, e2e et `scripts/audit.sh` verts.
**Contraintes globales** : Python 3.13 ; **aucune nouvelle dépendance runtime** (stdlib uniquement) ; domaine sans import technique ; aucune classe concrète instanciée hors de `container.py`.

| # revue | Tâche |
|---|---|
| 1 | T0 |
| 2 | T3 |
| 3, 4 | T2 |
| 5 | T1 |
| 6 | T4 |
| 7, 16 (CLI) | T6 |
| 8 | T7 |
| 9, 10, 11, 16 (licence) | T8 |
| 12 | T1 |
| 13 | T5 |
| 14 | T9 |
| 15 | T5 |
| 16 (README) | T10 |

---

### T0 — Dépôt Git (#1)
- Projet déplacé à la racine du dépôt `Examen/` (README visible directement sur GitHub), venv recréé.
- Commit de l'état initial, puis un commit par tâche. Aucune ligne `Co-Authored-By`.
- Push sur `origin/main` en fin de plan.

### T1 — Domaine : choix par jour + invariant de `Track` (#5, #12)
**Fichiers** : `domain/models.py`, `domain/rules.py`, `application/wake_up.py`, `infrastructure/users/in_memory.py`, `music/itunes.py`, `music/musicbrainz.py`, tests associés.
- `UserProfile.tracks_by_day: Mapping[tuple[DayOfWeek, Weather], str]` (défaut vide) : **surcharge facultative** jour + météo.
- `select_track_query(profile, day, weather)` : (jour, météo) → météo → morceau de secours.
- `Track.__post_init__` : `title` et `artist` doivent être des chaînes non vides, sinon `ValueError` (invariant métier, une seule garde par où passent tous les adapters).
- Adapters : `ValueError` ajouté aux erreurs de format → `ProviderUnavailable` → repli.
- Démo : `u1` a un morceau spécial le SAMEDI + SOLEIL.
**Tests** : surcharge jour prioritaire ; jour sans surcharge → météo ; `Track("", …)` et `Track(None, …)` refusés ; iTunes/MusicBrainz avec champ `null` → `ProviderUnavailable`.

### T2 — Jamais de silence côté canal et côté service utilisateurs (#3, #4)
**Fichiers** : `application/notifier.py`, `__main__.py`, tests.
- `NotificationDispatcher` : toute exception d'un sender (pas seulement `NotificationFailed`) est **journalisée avec sa trace** puis on passe au canal suivant. C'est le point unique par où passent tous les canaux, donc la correction couvre aussi les canaux futurs.
- `__main__` : `UnknownUser` → message clair + code 2 ; toute autre panne (service utilisateurs, bug) → `logging.critical("RÉVEIL NON LIVRÉ …")` + code 1, pour que l'ordonnanceur alerte/relance. Pas de trace brute.
**Tests** : sender qui lève `ConnectionError` → canal suivant ; CLI utilisateur inconnu → code 2 et message ; dépôt utilisateurs en panne → code 1 et log critique.

### T3 — Fournisseurs choisis par configuration, sans toucher au code (#2)
**Fichiers** : `container.py`, `tests/unit/test_container.py`.
- `REVEIL_MUSIC_PROVIDERS` (défaut `itunes,musicbrainz`) : ordre des sources distantes ; la liste locale est **toujours** ajoutée en dernier.
- Nom inconnu → `ValueError` explicite au démarrage (on échoue tôt plutôt qu'à 7 h).
**Tests** : `musicbrainz,itunes` inverse l'ordre ; `musicbrainz` seul ; nom inconnu refusé ; local toujours en dernier.

### T4 — Coupe-circuit (#6, J1 p.33)
**Fichiers** : `infrastructure/music/guards.py`, `container.py`, tests.
- `CircuitBreakerMusicProvider(inner, clock, failure_threshold=3, reset_seconds=60)` : après 3 échecs consécutifs, circuit **ouvert** → `ProviderUnavailable` immédiat (aucun appel réseau, donc aucune attente du timeout) ; après `reset_seconds`, un appel d'essai (**semi-ouvert**) : succès → fermé, échec → ré-ouvert.
- Chaîne par fournisseur : `cache → coupe-circuit → quota → adapter`.
**Tests** : ouverture après 3 échecs sans appel de l'inner ; un succès remet le compteur à zéro ; essai après délai, succès referme ; échec de l'essai ré-ouvre.

### T5 — Concurrence et données personnelles (#13, #15)
**Fichiers** : `guards.py`, `container.py`, `notifications/clients.py`, tests.
- `threading.Lock` autour de l'état du quota, du cache et du coupe-circuit (verrou tenu uniquement pendant la lecture/écriture de l'état, jamais pendant l'appel réseau).
- `providers.ThreadSafeSingleton` pour les composants à état partagé (`Singleton` de dependency-injector n'est pas thread-safe : deux réveils simultanés pourraient créer deux quotas).
- `User-Agent` par défaut : URL publique du dépôt au lieu d'un email personnel (accepté par MusicBrainz).
- Faux SDK : email/téléphone/jeton **masqués** dans les logs (`al***@example.com`, `+336******01`).
**Tests** : 50 threads contre un quota de 20 → exactement 20 appels ; masquage des contacts ; test de dépendance captive étendu à `ThreadSafeSingleton`.

### T6 — Cache et quota réellement partagés : mode lot (#7, #16 CLI)
**Fichiers** : `__main__.py`, tests, README.
- Constat : un processus par réveil ⇒ cache et quota repartent de zéro. La bonne réponse architecturale est que l'ordonnanceur appelle le use case **dans un processus unique** (conteneur construit une fois, singletons partagés).
- `python -m reveil_musical --batch reveils.csv` (`user,jour,meteo` par ligne) : un seul conteneur pour tous les réveils ; une ligne invalide ou en échec est journalisée et **n'empêche pas les suivantes**.
- Jour/météo acceptés sans tenir compte de la casse (`lundi`).
**Tests** : lot de 3 réveils sur le même morceau → **1 seul** appel HTTP (cache partagé) ; ligne invalide au milieu → les autres sont envoyées, code 1 ; `lundi soleil` accepté.

### T7 — Tests de contrat par abstraction + bout en bout (#8, J2 p.51)
**Fichiers** : `tests/contract/test_port_contracts.py`, `tests/e2e/test_real_apis.py`, `pyproject.toml`.
- **Contrat `MusicProvider`** appliqué à *toutes* les implémentations (iTunes, MusicBrainz, local, cache, quota, coupe-circuit) : renvoie `Track` ou `None`, ne lève que `ProviderUnavailable`.
- **Contrat `NotificationSender`** appliqué aux 4 implémentations (email, SMS, push, log) : `send(contact, message)` → `None`.
- **E2E** contre les vraies API (marqueur `e2e`, exclu par défaut, lancé via `pytest -m e2e --no-cov`) : iTunes, MusicBrainz, CLI complète.

### T8 — Contrôle licences/vulnérabilités automatisé + SBOM CycloneDX (#9, #10, #11, #16 licence)
**Fichiers** : `scripts/audit.sh`, `sbom.cdx.json`, `pyproject.toml`, README.
- `scripts/audit.sh` (bloquant) : `pip-licenses --fail-on "GPL;AGPL;LGPL;SSPL" --partial-match` ; `pip-audit --strict --skip-editable` ; génération `sbom.cdx.json` (CycloneDX) ; rapport `pip list --outdated` (informatif).
- `pyproject.toml` : `license = "LicenseRef-Proprietary"`.
- README : tableau **complet** des 48 paquets (version installée, dernière stable, licence, runtime/dev, direct/transitif).
**Vérification** : le script passe ; il échoue si on ajoute une licence GPL (essai de mutation).

### T9 — Test d'architecture renforcé (#14)
**Fichiers** : `tests/architecture/test_layers.py`.
- Détecte aussi `module.Classe(...)`.
- `infrastructure/` n'importe ni `application/` ni le conteneur.
**Tests** : auto-test du détecteur sur les deux nouvelles violations.

### T10 — README (#16) + push
- Retirer les chiffres codés en dur (nombre de tests, « ~40 lignes ») ; documenter la surcharge par jour, le coupe-circuit, le mode lot, la sélection par config, l'audit, l'e2e ; ajouter `logging` à l'inventaire J1 (dépendance implicite assumée).
- `pytest`, `pytest -m e2e --no-cov`, `scripts/audit.sh` verts → push.

## Points d'attention (non couverts par un test unitaire existant)
1. Timeout réseau réel (pas un refus) : le coupe-circuit doit éviter d'attendre 3 s à chaque réveil → T4.
2. Deux réveils concurrents au même instant → T5.
3. Lot avec une ligne corrompue → T6.
4. Réponse fournisseur syntaxiquement valide mais vide de sens (`null`) → T1.
5. Variable d'env erronée (`REVEIL_MUSIC_PROVIDERS=spotify`) → T3.
