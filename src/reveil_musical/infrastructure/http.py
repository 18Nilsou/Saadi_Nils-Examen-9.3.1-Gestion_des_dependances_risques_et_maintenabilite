"""Client HTTP JSON minimal (stdlib) : seul endroit qui connaît le transport réseau."""
import http.client
import json
import urllib.error
import urllib.parse
import urllib.request

from reveil_musical.domain.errors import ProviderUnavailable, QueryRejected


class JsonHttpClient:
    def __init__(self, timeout: float):
        self._timeout = timeout

    def get_json(self, url: str, params: dict | None = None, headers: dict | None = None) -> dict:
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(url, headers=headers or {})
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as e:
            # 4xx = notre requête est refusée (titre exotique…), pas une panne : ne doit pas couper la source.
            # 403 (bridage iTunes) et 429 (trop de requêtes) restent des pannes.
            error = QueryRejected if 400 <= e.code < 500 and e.code not in (403, 429) else ProviderUnavailable
            raise error(f"{url}: {e}") from e
        except (OSError, ValueError, http.client.HTTPException) as e:
            # OSError couvre URLError, timeouts ; ValueError couvre le JSON invalide.
            raise ProviderUnavailable(f"{url}: {e}") from e
