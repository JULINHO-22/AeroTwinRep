from collections.abc import Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_db
from app.main import app
from app.services.evidence_storage import EvidenceStorage, get_evidence_storage
from scripts.seed_demo import seed_demo


@pytest.fixture(scope="session")
def test_database_url() -> str:
    settings = get_settings()
    if not settings.test_database_url:
        raise RuntimeError("TEST_DATABASE_URL es obligatorio para los tests de integración.")

    database_name = make_url(settings.test_database_url).database or ""
    if not database_name.endswith("_test"):
        raise RuntimeError(
            "TEST_DATABASE_URL debe apuntar a una base cuyo nombre termine en _test."
        )
    return settings.test_database_url


@pytest.fixture(scope="session", autouse=True)
def migrated_database(test_database_url: str) -> Generator[None, None, None]:
    backend_dir = Path(__file__).resolve().parents[1]
    alembic_config = Config(str(backend_dir / "alembic.ini"))
    alembic_config.set_main_option("sqlalchemy.url", test_database_url)

    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")
    seed_demo(test_database_url)
    yield


@pytest.fixture(scope="session")
def test_engine(test_database_url: str) -> Generator[Engine, None, None]:
    engine = create_engine(test_database_url, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture
def api_client(test_database_url: str, test_engine: Engine, tmp_path: Path) -> Generator[TestClient, None, None]:
    seed_demo(test_database_url)

    def override_get_db() -> Generator[Session, None, None]:
        with Session(test_engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_evidence_storage] = lambda: EvidenceStorage(tmp_path / "evidence")
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_evidence_storage, None)
