from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

TMP_DIR = Path(tempfile.mkdtemp(prefix="sql_station_tests_"))
os.environ["SQL_ADMIN_DATA_DIR"] = str(TMP_DIR)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

DB_PATH = TMP_DIR / "demo.db"


@pytest.fixture(scope="module")
def client():
    connection = sqlite3.connect(DB_PATH)
    connection.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT,
            age INTEGER,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            amount NUMERIC(10, 2) NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        INSERT INTO users (name, email, age, active) VALUES
            ('Alice', 'alice@example.com', 30, 1),
            ('Bob', 'bob@example.com', 24, 0);
        INSERT INTO orders (user_id, amount) VALUES (1, 99.50);
        CREATE VIEW active_users AS SELECT id, name FROM users WHERE active = 1;
        """
    )
    connection.commit()
    connection.close()
    with TestClient(app) as test_client:
        yield test_client


def _create_connection(client: TestClient, name: str = "本地 SQLite") -> dict:
    response = client.post(
        "/api/connections",
        json={
            "name": name,
            "kind": "sqlite",
            "sqlite_path": str(DB_PATH),
            "read_only": False,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_health(client: TestClient):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_connection_crud_and_test(client: TestClient):
    created = _create_connection(client)
    assert created["has_password"] is False
    assert created["name"] == "本地 SQLite"

    duplicate = client.post(
        "/api/connections",
        json={"name": created["name"], "kind": "sqlite", "sqlite_path": str(DB_PATH)},
    )
    assert duplicate.status_code == 409

    listed = client.get("/api/connections").json()
    assert len(listed) >= 1

    tested = client.post(
        "/api/connections/test",
        json={
            "id": created["id"],
            "name": created["name"],
            "kind": "sqlite",
            "sqlite_path": str(DB_PATH),
        },
    )
    assert tested.status_code == 200
    assert tested.json()["ok"] is True
    assert tested.json()["version"]

    updated = client.put(
        f"/api/connections/{created['id']}",
        json={"name": "Demo SQLite", "read_only": False},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Demo SQLite"


def test_catalog_tables_and_detail(client: TestClient):
    connection = _create_connection(client, "catalog-test")

    catalogs = client.get(f"/api/connections/{connection['id']}/catalogs").json()
    assert catalogs["kind"] == "sqlite"
    assert "main" in catalogs["databases"]

    tables = client.get(f"/api/connections/{connection['id']}/tables").json()
    names = [table["name"] for table in tables["tables"]]
    views = [view["name"] for view in tables["views"]]
    assert {"users", "orders"}.issubset(set(names))
    assert "active_users" in views

    detail = client.get(f"/api/connections/{connection['id']}/tables/users").json()
    assert detail["primary_key"] == ["id"]
    assert [column["name"] for column in detail["columns"]][:2] == ["id", "name"]
    assert detail["ddl"] and "CREATE TABLE users" in detail["ddl"]
    assert detail["foreign_keys"] == []

    order_detail = client.get(f"/api/connections/{connection['id']}/tables/orders").json()
    assert order_detail["foreign_keys"][0]["referred_table"] == "users"

    overview = client.get(f"/api/connections/{connection['id']}/overview").json()
    assert overview["table_count"] == 2
    assert overview["view_count"] == 1
    assert overview["size_bytes"] > 0


def test_rows_and_mutations(client: TestClient):
    connection = _create_connection(client, "rows-test")
    base = f"/api/connections/{connection['id']}/tables/users"

    rows = client.get(f"{base}/rows", params={"page": 1, "page_size": 10}).json()
    assert rows["total"] == 2
    assert rows["page_size"] == 10
    assert rows["primary_key"] == ["id"]

    filtered = client.get(f"{base}/rows", params={"where": "name = 'Alice'"}).json()
    assert filtered["total"] == 1
    assert filtered["rows"][0][1] == "Alice"

    sorted_rows = client.get(f"{base}/rows", params={"order_by": "age", "order_dir": "desc"}).json()
    assert sorted_rows["rows"][0][1] == "Alice"

    created = client.post(
        f"{base}/rows",
        json={"values": {"name": "Carol", "email": "carol@example.com", "age": 28}},
    )
    assert created.status_code == 201, created.text
    carol_id = created.json()["inserted"]["id"]

    updated = client.put(
        f"{base}/rows",
        json={"pk": {"id": carol_id}, "values": {"age": 29, "email": None}},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["affected"] == 1

    check = client.get(f"{base}/rows", params={"where": f"id = {carol_id}"}).json()
    assert check["rows"][0][3] == 29
    assert check["rows"][0][2] is None

    deleted = client.request(
        "DELETE",
        f"{base}/rows",
        json={"pk": {"id": carol_id}},
    )
    assert deleted.status_code == 200, deleted.text
    assert client.get(f"{base}/rows").json()["total"] == 2


def test_query_and_read_only(client: TestClient):
    connection = _create_connection(client, "query-test")
    query_url = f"/api/connections/{connection['id']}/query"

    result = client.post(
        query_url,
        json={"sql": "SELECT id, name FROM users ORDER BY id; SELECT COUNT(*) AS n FROM orders;"},
    )
    assert result.status_code == 200, result.text
    payload = result.json()
    assert payload["ok"] is True
    assert len(payload["results"]) == 2
    assert payload["results"][0]["rows"][0][1] == "Alice"
    assert payload["results"][1]["rows"][0][0] == 1

    updated = client.put(
        f"/api/connections/{connection['id']}", json={"read_only": True}
    ).json()
    assert updated["read_only"] is True

    blocked = client.post(query_url, json={"sql": "DELETE FROM users"})
    assert blocked.status_code == 403

    allowed = client.post(query_url, json={"sql": "SELECT COUNT(*) FROM users"})
    assert allowed.status_code == 200
    assert allowed.json()["ok"] is True

    blocked_mutation = client.put(
        f"/api/connections/{connection['id']}/tables/users/rows",
        json={"pk": {"id": 1}, "values": {"name": "Hacker"}},
    )
    assert blocked_mutation.status_code == 403

    bad_sql = client.post(query_url, json={"sql": "SELECT * FROM missing_table"})
    assert bad_sql.status_code == 200
    assert bad_sql.json()["ok"] is False
    assert "missing_table" in bad_sql.json()["error"]


def test_export_csv(client: TestClient):
    connection = _create_connection(client, "export-test")
    response = client.get(
        f"/api/connections/{connection['id']}/tables/users/export",
        params={"order_by": "id"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    text = response.content.decode("utf-8-sig")
    assert text.splitlines()[0] == "id,name,email,age,active,created_at"
    assert "Alice" in text


def test_sql_splitter():
    from app.services.executor import split_sql

    assert split_sql("SELECT ';'; -- note\nSELECT 2;") == [
        "SELECT ';'",
        "-- note\nSELECT 2",
    ]
    assert split_sql("-- only a comment\n;") == []
    assert split_sql("SELECT $$a;b$$;") == ["SELECT $$a;b$$"]
    assert split_sql("SELECT 1; /* trailing */") == ["SELECT 1"]


def test_read_only_cte_guard(client: TestClient):
    connection = _create_connection(client, "readonly-cte")
    client.put(f"/api/connections/{connection['id']}", json={"read_only": True})
    query_url = f"/api/connections/{connection['id']}/query"

    allowed = client.post(
        query_url,
        json={"sql": "WITH active AS (SELECT id FROM users WHERE active = 1) SELECT * FROM active"},
    )
    assert allowed.status_code == 200
    assert allowed.json()["ok"] is True

    blocked = client.post(
        query_url,
        json={"sql": "WITH x AS (SELECT 1) INSERT INTO users(name) SELECT 'intruder'"},
    )
    assert blocked.status_code == 403


def test_connection_urls():
    from app.models import Connection
    from app.services.connections import build_url

    mysql = build_url(
        Connection(
            name="mysql",
            kind="mysql",
            host="db.example.com",
            port=3306,
            username="app",
            database="shop",
            options={"charset": "utf8mb4"},
        )
    )
    assert mysql.drivername == "mysql+pymysql"
    assert mysql.host == "db.example.com"
    assert mysql.database == "shop"
    assert mysql.query["charset"] == "utf8mb4"

    postgres = build_url(
        Connection(
            name="pg",
            kind="postgresql",
            host="pg.example.com",
            port=5432,
            username="app",
            database="analytics",
        )
    )
    assert postgres.drivername == "postgresql+pg8000"
    assert postgres.database == "analytics"

    sqlite = build_url(Connection(name="sqlite", kind="sqlite", sqlite_path=str(DB_PATH)))
    assert sqlite.drivername == "sqlite"
    assert sqlite.database.endswith("demo.db")
