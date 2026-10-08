# Réveil musical

Chaque utilisateur est réveillé avec un morceau choisi selon **le jour** et **la météo**, puis prévenu sur **son canal préféré** (email, SMS, push).
Le TP porte sur l'appel déclenché à l'heure du réveil : `WakeUpUseCase.execute(user_id, jour, météo)`.

```bash
brew install python@3.13
python3.13 -m venv .venv && .venv/bin/pip install -e ".[dev]"

.venv/bin/python -m reveil_musical u1 LUNDI SOLEIL      # u1=email, u2=sms, u3=push
.venv/bin/pytest                                          # 95 tests, couverture ≥ 90 % imposée (99,7 % actuellement)
```

---

## 1. Des exigences métier aux choix techniques

| Exigence (sujet) | Traduction technique |
|---|---|
| Changer **vite** de fournisseur musical | Port `MusicProvider` + un **Adapter** par source. L'ordre des sources se décide dans `container.py` et nulle part ailleurs. |
| Plusieurs **canaux** de notification, d'autres à venir | Port `NotificationSender` + un **Adapter** par SDK (3 faux SDK aux signatures différentes). `NotificationDispatcher` (**Strategy**) choisit selon le profil. |
| **Aucune** dépendance sans contrôle licence / fraîcheur | Une seule dépendance runtime ; SBOM complet en §5 ; versions épinglées (`pyproject.toml`, `requirements-dev.lock`) ; `pip-audit` sans vulnérabilité. |
| **Jamais** de silence | Musique : **chaîne de repli** iTunes → MusicBrainz → liste locale. Canal : préféré → autres canaux connus de l'utilisateur → log de dernier recours. `WakeUpResult.degraded` signale le mode dégradé. |

## 2. Architecture

```
            ┌─────────────────────────── container.py (composition root) ───────────────────────────┐
            │   seul fichier qui connaît les classes concrètes et les assemble (dependency-injector) │
            └────────────────────────────────────────────────────────────────────────────────────────┘
 __main__ ──►  application/                     domain/  (aucune dépendance technique)
               WakeUpUseCase ──────────────────► rules.py   : choix du morceau, formatage du message
               MusicFallbackChain ─────────────► ports.py   : MusicProvider, NotificationSender,
               NotificationDispatcher                         UserPreferencesRepository, Clock
                                                 models.py  : Track(title, artist, source), UserProfile…
               infrastructure/  ─── implémente les ports ───►
               music/ itunes · musicbrainz · local · guards (cache + quota)
               notifications/ clients (faux SDK) · adapters
               users/ in_memory (mock du service interne)   http.py (urllib)   clock.py
```

Les flèches vont toujours vers le domaine : **l'infrastructure dépend du domaine, jamais l'inverse**. Ces règles sont vérifiées à chaque exécution des tests (`tests/architecture/test_layers.py`) :
- `domain/` n'importe que `collections`, `dataclasses`, `enum`, `typing` ;
- `application/` n'importe ni `infrastructure`, ni le conteneur, ni un module réseau ou JSON ;
- aucune classe d'`infrastructure` n'est instanciée hors de `container.py` (« pas de `new` »).

**Aucune fuite de DTO** : le JSON iTunes (`trackName`, `trackViewUrl`…) et MusicBrainz (`title`, `artist-credit`) est converti en `Track` *dans* l'adapter. `Track` n'a que `title`, `artist`, `source` (testé). Les erreurs réseau et les formats inattendus deviennent `ProviderUnavailable`, une erreur du domaine.

### Patterns utilisés (et le problème qu'ils règlent)

| Pattern | Où | Problème |
|---|---|---|
| Adapter | `music/itunes.py`, `music/musicbrainz.py`, `notifications/adapters.py` | API externes au format différent du modèle interne |
| Strategy | `NotificationDispatcher` | un comportement d'envoi choisi au runtime selon le profil |
| Chain of Responsibility | `MusicFallbackChain` | repli ordonné entre fournisseurs |
| Decorator | `music/guards.py` (`CachingMusicProvider`, `RateLimitedMusicProvider`) | quota iTunes (~20 req/min) et MusicBrainz (1 req/s) sans toucher aux adapters |

### Résilience

```
morceau :  cache ─► quota ─► iTunes  ──(panne / quota / rien trouvé)──►  cache ─► quota ─► MusicBrainz ──►  liste locale (renvoie toujours un morceau)
canal   :  canal préféré ──(NotificationFailed)──► autres canaux renseignés de l'utilisateur ──► LogNotificationSender (dernier recours)
```
- Le quota atteint lève immédiatement `ProviderUnavailable` : on **bascule au lieu d'attendre**, le réveil a une heure précise.
- Le cache est placé **devant** le quota : une requête déjà connue ne consomme pas le quota (testé).
- Le cache garde aussi les « non trouvé », pas les pannes.

### IoC / DI et durées de vie (`container.py`)

| Composant | Durée de vie | Raison |
|---|---|---|
| `JsonHttpClient`, `SystemClock`, adapters musique + caches + quotas, faux SDK + adapters notif, dépôt utilisateurs | **Singleton** | sans état par réveil, ou état qui **doit** être partagé : un quota recréé à chaque appel ne limiterait rien |
| `MusicFallbackChain`, `NotificationDispatcher`, `WakeUpUseCase` | **Factory (transient)** | orchestrations légères, sans état |
| Scoped | non utilisé | aucun état « par réveil » à partager |

**Dépendance captive** : un singleton ne dépend que de singletons, de la configuration ou de constantes. C'est vérifié par `test_no_captive_dependency_singletons_only_depend_on_singletons_or_config`, et le test échoue bien si l'on passe `http` en Factory.

### Configuration (dépendances implicites, rendues explicites)

| Variable | Défaut |
|---|---|
| `REVEIL_ITUNES_URL` | `https://itunes.apple.com` |
| `REVEIL_MUSICBRAINZ_URL` | `https://musicbrainz.org` |
| `REVEIL_MUSICBRAINZ_USER_AGENT` | `ReveilMusical/0.1 (nils.saadi@gmail.com)` (exigé par MusicBrainz) |
| `REVEIL_HTTP_TIMEOUT` | `3.0` s |
| `REVEIL_CACHE_TTL` | `86400` s |

Démonstration du mode dégradé : `REVEIL_ITUNES_URL=http://127.0.0.1:9 python -m reveil_musical u2 MARDI PLUIE` (bascule sur MusicBrainz) ; ajoutez `REVEIL_MUSICBRAINZ_URL=http://127.0.0.1:9` pour tomber sur la liste locale.

### Faire évoluer

- **Nouveau canal (ex. WhatsApp)** : 1 valeur `Channel.WHATSAPP` + 1 adapter qui implémente `send(contact, message)` + 1 ligne dans `providers.Dict` du conteneur. Le use case ne change pas.
- **Nouvelle source musicale (ex. Deezer)** : 1 adapter `find_track(query) -> Track | None` + 1 entrée dans `providers.List` (à n'importe quelle position). Le use case ne change pas.

## 3. Tests

| Dossier | Ce qui est garanti |
|---|---|
| `tests/unit/` | règles du domaine ; use case avec fakes (nominal, météo non couverte → morceau de secours, panne musique → local, panne canal → autre canal, panne totale → dernier recours) ; cache, quota, chaîne de repli ; dispatcher ; adapters de notification (signatures hétérogènes, SMS tronqué à 160 car., erreurs SDK → `NotificationFailed`) ; conteneur (résolution, durées de vie, dépendance captive, `override` par des fakes, variables d'env, CLI) |
| `tests/contract/` | adapters iTunes / MusicBrainz contre des **réponses réelles enregistrées** (`tests/fixtures/`) : mapping, `User-Agent`, résultat vide, HTTP 500, timeout, JSON inattendu, pas de fuite de DTO ; `JsonHttpClient` contre un serveur HTTP **local** (200, 500, HTML, timeout, hôte injoignable) |
| `tests/architecture/` | règles de couches et « pas de `new` » (voir §2) |

Aucun test n'accède à Internet. Les seams utilisés sont les ports du domaine et `JsonHttpClient` (remplacé par `FakeHttp`), plus `Clock` (remplacé par `FakeClock` : les tests de quota et de TTL n'attendent pas).

## 4. Inventaire des dépendances (méthode J1)

| Dépendance | Interne / externe | Directe / transitive | Explicite / implicite | Couplage | Contrôle |
|---|---|---|---|---|---|
| iTunes Search API | externe (réseau) | directe | explicite (URL) | **faible** : 1 adapter | aucun : sans SLA, ~20 req/min |
| MusicBrainz API | externe (réseau) | directe | explicite + en-tête `User-Agent` obligatoire | **faible** : 1 adapter | aucun : 1 req/s |
| Service utilisateurs (mock) | interne | directe | explicite (port) | faible | total |
| SDK email / SMS / push (mocks) | externe simulé | directe | explicite (port) | faible : 1 adapter chacun | total (simulé) |
| `dependency-injector` | externe (package) | directe | explicite | **confiné à `container.py`** | voir §5 |
| Bibliothèque standard Python (`urllib`, `json`, `logging`) | externe (runtime) | directe | explicite | faible : `http.py` seulement | élevé |
| Variables `REVEIL_*` | — | — | **implicite** → documentée (§2) et testée | faible | total |
| Horloge système | — | — | **implicite** → port `Clock` injecté | faible | total |
| Accès réseau sortant (DNS, TLS) | externe | transitive | implicite | — | aucun, compensé par la chaîne de repli |

**SPOF neutralisés** : chaque fournisseur musical et chaque canal est derrière une interface, doublé, et le dernier maillon (liste locale, log) ne dépend d'aucun réseau.

## 5. SBOM & audit (au 2026-10-08)

Commandes utilisées : `pip-licenses --format=markdown --with-urls`, `pipdeptree`, `pip list --outdated` (aucun paquet en retard), `pip-audit` (**aucune vulnérabilité connue**). L'environnement complet est figé dans `requirements-dev.lock` (48 paquets).

### Plateforme

| Composant | Version installée | Dernière stable | Licence | Commentaire |
|---|---|---|---|---|
| CPython | 3.13.16 | 3.14.8 | PSF-2.0 (permissive) | Le Python 3.9 du système est **en fin de vie** (oct. 2025) : écarté. 3.13 reçoit des correctifs de sécurité jusqu'en oct. 2029. Passer à 3.14 est possible, mais pas encore testé. |

### Runtime (livré avec le produit)

| Package | Rôle | Version installée | Dernière stable | Licence | Transitives | Vulnérabilités |
|---|---|---|---|---|---|---|
| `dependency-injector` | conteneur IoC (durées de vie, override en test) | 4.49.1 | 4.49.1 | BSD-3-Clause (permissive) | **aucune** | aucune |

HTTP : bibliothèque standard (`urllib`), soit **zéro paquet de plus** à auditer. `requests` ou `httpx` n'apportaient rien d'utile ici (timeout et en-têtes suffisent).

**Point d'attention, le « bus factor »** : `dependency-injector` repose surtout sur un seul mainteneur (cf. J2, pérennité). On l'accepte parce que son usage est **confiné à `container.py`** : le domaine, l'application et l'infrastructure n'en savent rien. S'il fallait le remplacer, une composition root écrite à la main (~40 lignes) suffirait, sans toucher au reste.

### Développement (non livré)

| Package | Rôle | Version installée | Dernière stable | Licence |
|---|---|---|---|---|
| `pytest` | tests | 9.1.1 | 9.1.1 | MIT |
| `pytest-cov` (+ `coverage` 7.16.2) | couverture | 7.1.0 | 7.1.0 | MIT (+ Apache-2.0) |
| `pip-audit` | vulnérabilités | 2.10.1 | 2.10.1 | Apache-2.0 |
| `pip-licenses` | licences | 5.5.5 | 5.5.5 | MIT |
| `pipdeptree` | arbre des dépendances | 4.2.5 | 4.2.5 | MIT |

Transitives de dev (pytest, pip-audit, pip-licenses, pipdeptree) : toutes permissives, sauf deux cas à justifier :
- MIT : `build`, `charset-normalizer`, `filelock`, `iniconfig`, `installer`, `markdown-it-py`, `mdurl`, `nab*`, `packageurl-python`, `pip-requirements-parser`, `platformdirs`, `pluggy`, `pyparsing`, `pyproject_hooks`, `rich`, `tomli`, `tomli_w`, `truststore`, `urllib3`, `wcwidth` ;
- Apache-2.0 : `CacheControl`, `cyclonedx-python-lib`, `license-expression`, `msgpack`, `pip_api`, `py-serializable`, `requests`, `sortedcontainers` ;
- BSD : `boolean.py`, `idna`, `prettytable`, `Pygments` ; `packaging` (Apache-2.0 OR BSD-2) ; PSF : `defusedxml`, `typing_extensions` ;
- ⚠️ **`certifi` 2026.7.22, MPL-2.0** : copyleft *faible*, fichier par fichier. Il n'est utilisé que par l'outillage de dev (`pip-audit` → `requests`), n'est **ni modifié ni distribué** avec le produit : aucune obligation ne s'applique. Accepté.

**Copyleft fort (GPL / AGPL) : aucun**, ni en runtime ni en dev.

### Services externes

| Service | Conditions | Risque (J2) | Mitigation |
|---|---|---|---|
| iTunes Search API | gratuit, sans clé, ~20 req/min, sans SLA, CGU Apple | **pricing / fin de vie** décidés seuls par Apple ; **souveraineté** : opérateur US (Cloud Act), mais aucune donnée personnelle envoyée (seulement le titre du morceau) | Adapter isolé, cache + quota, repli automatique |
| MusicBrainz API | gratuit, `User-Agent` identifiable obligatoire, 1 req/s ; données principales en CC0 | usage **commercial** : MetaBrainz demande aux entreprises de soutenir le projet (plan payant). **À valider par le juridique avant la mise en production.** | Adapter isolé, quota 1 req/s, repli local |

## 6. Limites connues

- La pertinence de MusicBrainz est variable : on prend le premier résultat (ex. « Purple Rain » renvoie une reprise peu connue). On pourrait filtrer par score ou par artiste, mais ce n'est pas demandé.
- Le cache est en mémoire et non borné (`ponytail:` dans `guards.py`). Passer à un LRU ou à Redis si le volume l'exige.
- Les canaux de notification sont des mocks qui écrivent dans le log, comme le demande le sujet.
- Ce sont les profils de démo qui fixent l'ordre de repli entre canaux (ordre des contacts de l'utilisateur).
