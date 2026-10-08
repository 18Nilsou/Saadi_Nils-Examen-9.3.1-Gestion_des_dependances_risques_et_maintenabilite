"""Garde-fous d'architecture : la règle des couches et le « pas de new » sont vérifiés à chaque build."""
import ast
from pathlib import Path

import pytest

SRC = Path(__file__).parents[2] / "src" / "reveil_musical"
DOMAIN_ALLOWED = {"collections", "dataclasses", "enum", "typing"}
TECHNICAL = {"urllib", "json", "http", "socket", "requests", "httpx", "dependency_injector", "logging"}


def modules(layer: str) -> list[Path]:
    return sorted((SRC / layer).rglob("*.py"))


def package_of(path: Path) -> str:
    return ".".join(path.relative_to(SRC.parent).parent.parts)


def imports_of(source: str, package: str | None = None) -> set[str]:
    """Modules importés. Sans `package`, les imports relatifs restent préfixés par '.' ;
    avec `package`, ils sont résolus en absolu (ex. '...application' -> 'reveil_musical.application')."""
    found = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            if node.level and package:
                base = package.split(".")[: len(package.split(".")) - node.level + 1]
                found.add(".".join(base + ([node.module] if node.module else [])))
            else:
                found.add("." * node.level + (node.module or ""))
    return found


def infrastructure_classes() -> set[str]:
    return {
        node.name
        for path in modules("infrastructure")
        for node in ast.walk(ast.parse(path.read_text()))
        if isinstance(node, ast.ClassDef) and not node.name.endswith(("Error", "Rejected"))
    }


def instantiations(source: str, class_names: set[str]) -> set[str]:
    """Appels `Classe(...)` ou `module.Classe(...)` d'une des classes données."""
    called = {
        node.func.id if isinstance(node.func, ast.Name) else node.func.attr
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call) and isinstance(node.func, (ast.Name, ast.Attribute))
    }
    return called & class_names


def test_detectors_catch_a_violation():
    bad = "import json\nfrom reveil_musical.infrastructure.http import JsonHttpClient\nJsonHttpClient(1)"
    assert {"json", "reveil_musical.infrastructure.http"} <= imports_of(bad)
    assert instantiations(bad, {"JsonHttpClient"}) == {"JsonHttpClient"}


def test_detectors_catch_qualified_instantiation_and_resolve_relative_imports():
    assert instantiations("from .. import http\nhttp.JsonHttpClient(1)", {"JsonHttpClient"}) == {"JsonHttpClient"}
    relative = "from ...application.notifier import NotificationDispatcher"
    assert "reveil_musical.application.notifier" in imports_of(relative, "reveil_musical.infrastructure.music")


@pytest.mark.parametrize("path", modules("domain"), ids=lambda p: p.name)
def test_domain_depends_on_nothing_but_pure_stdlib(path):
    for name in imports_of(path.read_text()):
        if name.startswith("."):
            assert name.count(".") == 1, f"{path.name} sort du domaine : {name}"
        else:
            assert name.split(".")[0] in DOMAIN_ALLOWED, f"{path.name} importe {name}"


@pytest.mark.parametrize("path", modules("application"), ids=lambda p: p.name)
def test_application_never_reaches_infrastructure(path):
    for name in imports_of(path.read_text()):
        assert "infrastructure" not in name and "container" not in name, f"{path.name} importe {name}"
        assert name.split(".")[0] not in TECHNICAL - {"logging"}, f"{path.name} importe {name}"


@pytest.mark.parametrize("path", modules("infrastructure"), ids=lambda p: str(p.relative_to(SRC)))
def test_infrastructure_depends_on_the_domain_never_on_application_or_container(path):
    for name in imports_of(path.read_text(), package_of(path)):
        assert not name.startswith(("reveil_musical.application", "reveil_musical.container")), f"{path.name} importe {name}"


@pytest.mark.parametrize(
    "path", [p for p in SRC.rglob("*.py") if p.name != "container.py"], ids=lambda p: str(p.relative_to(SRC))
)
def test_no_concrete_infrastructure_class_is_instantiated_outside_the_container(path):
    assert instantiations(path.read_text(), infrastructure_classes()) == set()
