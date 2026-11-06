import os
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from testcontainers.postgres import PostgresContainer

from acwa.config import DEV_FERNET_KEY, Settings, clear_settings_cache
from acwa.db import reset_engine

pytestmark = pytest.mark.integration


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    container = PostgresContainer("postgres:16-alpine")
    container.start()
    raw = container.get_connection_url().replace("postgresql+psycopg2://", "postgresql+psycopg://")
    if raw.startswith("postgresql://"):
        raw = raw.replace("postgresql://", "postgresql+psycopg://", 1)
    url = raw
    os.environ["ACWA_DATABASE_URL"] = url
    os.environ["ACWA_INTEGRATION_MODE"] = "demo"
    os.environ["ACWA_DEMO_SEED"] = "false"
    os.environ["ACWA_TOKEN_ENCRYPTION_KEY"] = DEV_FERNET_KEY
    os.environ["ACWA_AUTH_TOKEN"] = "integration-test-password"
    os.environ["ACWA_DEEPSEEK_API_KEY"] = "sk-integration-secret-should-not-leak"
    clear_settings_cache()
    reset_engine()
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    yield url
    reset_engine()
    clear_settings_cache()
    container.stop()


@pytest.fixture
def settings(postgres_url: str) -> Settings:
    return Settings(
        database_url=postgres_url,
        integration_mode="demo",
        demo_seed=False,
        token_encryption_key=DEV_FERNET_KEY,
        deepseek_api_key="sk-integration-secret-should-not-leak",
        auth_token="integration-test-password",
    )


@pytest.fixture
def session_factory(postgres_url: str) -> Iterator[sessionmaker[Session]]:
    engine = create_engine(postgres_url)
    factory = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)
    yield factory
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_database(postgres_url: str) -> Iterator[None]:
    yield
    engine = create_engine(postgres_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE post_attempts, jobs, skipped_slots, posts, campaigns, "
                "oauth_states, app_settings, threads_accounts RESTART IDENTITY CASCADE"
            )
        )
    engine.dispose()


@pytest.fixture
def app(settings: Settings, postgres_url: str):
    reset_engine()
    clear_settings_cache()
    os.environ["ACWA_DATABASE_URL"] = postgres_url
    from acwa.main import create_app

    application = create_app(settings)
    yield application
    reset_engine()
    clear_settings_cache()


@pytest.fixture
def client(app, settings: Settings) -> Iterator[TestClient]:
    with TestClient(app, headers={"Authorization": f"Bearer {settings.auth_token}"}) as test_client:
        yield test_client
