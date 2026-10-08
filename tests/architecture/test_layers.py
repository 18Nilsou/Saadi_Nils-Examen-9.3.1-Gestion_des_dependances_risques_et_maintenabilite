"""Garde-fous d'architecture : la règle des couches et le « pas de new » sont vérifiés à chaque build."""
import ast
from pathlib import Path

import pytest

SRC = Path(__file__).parents[2] / "src" / "reveil_musical"
DOMAIN_ALLOWED = {"collections", "dataclasses", "enum", "typing"}
TECHNICAL = {"urllib", "json", "http", "socket", "requests", "httpx", "dependency_injector", "logging"}


def modules(layer: str) -> list[Path]:
    return sorted((SRC / layer).rglob("*.py"))


def imports_of(source: str) -> set[str]:
    """Modules importés en absolu ('reveil_musical.x', 'json'…) ; les imports relatifs sont préfixés par '.'."""
    found = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
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
    return {
        node.func.id
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in class_names
    }


def test_detectors_catch_a_violation():
    bad = "import json\nfrom reveil_musical.infrastructure.http import JsonHttpClient\nJsonHttpClient(1)"
    assert {"json", "reveil_musical.infrastructure.http"} <= imports_of(bad)
    assert instantiations(bad, {"JsonHttpClient"}) == {"JsonHttpClient"}


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


@pytest.mark.parametrize(
    "path", [p for p in SRC.rglob("*.py") if p.name != "container.py"], ids=lambda p: str(p.relative_to(SRC))
)
def test_no_concrete_infrastructure_class_is_instantiated_outside_the_container(path):
    assert instantiations(path.read_text(), infrastructure_classes()) == set()
