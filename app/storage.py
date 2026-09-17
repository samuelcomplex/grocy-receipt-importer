from __future__ import annotations

from contextlib import contextmanager
import os
import sqlite3
from typing import Protocol

from app.config import DATA_DIR, DB_PATH


class ReceiptStorage(Protocol):
    def get(self, receipt_id: str):
        ...

    def list_recent(self, limit: int = 20):
        ...

    def save(self, receipt):
        ...

    def update(self, receipt_id: str, **fields):
        ...

    def delete(self, receipt_id: str):
        ...

    def find_by_hash(self, sha256: str):
        ...


class MappingStorage(Protocol):
    def get(self, store_org: str, article_number: str):
        ...

    def save(
        self,
        store_org: str,
        article_number: str,
        grocy_product_id: int,
        grocy_product_name: str,
    ):
        ...

    def delete(self, store_org: str, article_number: str):
        ...


class AliasStorage(Protocol):
    def get(self, store_org: str, normalized_description: str):
        ...

    def save(
        self,
        store_org: str,
        normalized_description: str,
        grocy_product_id: int | None,
        grocy_product_name: str,
        ignored: bool = False,
    ):
        ...

    def delete(self, store_org: str, normalized_description: str):
        ...


def db():
    os.makedirs(DATA_DIR, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


@contextmanager
def db_connection():
    con = db()
    try:
        yield con
    finally:
        con.close()


def _init_sqlite_db():
    with db_connection() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS receipts (
                id TEXT PRIMARY KEY,
                sha256 TEXT UNIQUE NOT NULL,
                filename TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                items_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'review',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS mappings (
                store_org TEXT NOT NULL,
                article_number TEXT NOT NULL,
                grocy_product_id INTEGER NOT NULL,
                grocy_product_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY(store_org, article_number)
            );

            CREATE TABLE IF NOT EXISTS aliases (
                store_org TEXT NOT NULL,
                normalized_description TEXT NOT NULL,
                grocy_product_id INTEGER,
                grocy_product_name TEXT NOT NULL DEFAULT '',
                ignored INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                PRIMARY KEY(store_org, normalized_description)
            );
        """)
        alias_columns = {
            row["name"]
            for row in con.execute("PRAGMA table_info(aliases)").fetchall()
        }

        ignored_exists = con.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = 'ignored_items'
            """
        ).fetchone()

        product_id_not_null = any(
            row["name"] == "grocy_product_id" and row["notnull"]
            for row in con.execute("PRAGMA table_info(aliases)").fetchall()
        )

        if "ignored" not in alias_columns or product_id_not_null:
            con.execute("ALTER TABLE aliases RENAME TO aliases_legacy")
            con.execute(
                """
                CREATE TABLE aliases (
                    store_org TEXT NOT NULL,
                    normalized_description TEXT NOT NULL,
                    grocy_product_id INTEGER,
                    grocy_product_name TEXT NOT NULL DEFAULT '',
                    ignored INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(store_org, normalized_description)
                )
                """
            )
            con.execute(
                """
                INSERT INTO aliases (
                    store_org,
                    normalized_description,
                    grocy_product_id,
                    grocy_product_name,
                    ignored,
                    created_at
                )
                SELECT
                    store_org,
                    normalized_description,
                    grocy_product_id,
                    grocy_product_name,
                    0,
                    created_at
                FROM aliases_legacy
                """
            )
            con.execute("DROP TABLE aliases_legacy")

        if ignored_exists:
            con.execute(
                """
                UPDATE aliases
                SET ignored = 1,
                    grocy_product_id = NULL,
                    grocy_product_name = ''
                WHERE (store_org, normalized_description) IN (
                    SELECT store_org, normalized_description
                    FROM ignored_items
                )
                """
            )
            con.execute(
                """
                INSERT OR IGNORE INTO aliases (
                    store_org,
                    normalized_description,
                    grocy_product_id,
                    grocy_product_name,
                    ignored,
                    created_at
                )
                SELECT
                    store_org,
                    normalized_description,
                    NULL,
                    '',
                    1,
                    created_at
                FROM ignored_items
                """
            )
            con.execute("DROP TABLE ignored_items")

        con.commit()


class SQLiteReceiptStorage:
    def __init__(self):
        _init_sqlite_db()

    def get(self, receipt_id: str):
        with db_connection() as con:
            return con.execute(
                "SELECT * FROM receipts WHERE id = ?",
                (receipt_id,),
            ).fetchone()

    def list_recent(self, limit: int = 20):
        with db_connection() as con:
            return con.execute(
                """
                SELECT id, filename, metadata_json, items_json, status, created_at
                FROM receipts
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

    def save(self, receipt):
        with db_connection() as con:
            con.execute(
                """
                INSERT INTO receipts (
                    id,
                    sha256,
                    filename,
                    raw_text,
                    metadata_json,
                    items_json,
                    status,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    receipt["id"],
                    receipt["sha256"],
                    receipt["filename"],
                    receipt["raw_text"],
                    receipt["metadata_json"],
                    receipt["items_json"],
                    receipt["status"],
                    receipt["created_at"],
                ),
            )
            con.commit()

    def update(self, receipt_id: str, **fields):
        if not fields:
            return

        allowed = {
            "filename",
            "raw_text",
            "metadata_json",
            "items_json",
            "status",
            "created_at",
            "sha256",
        }

        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"Unknown receipt fields: {sorted(unknown)}")

        assignments = ", ".join(f"{field} = ?" for field in fields)

        with db_connection() as con:
            con.execute(
                f"UPDATE receipts SET {assignments} WHERE id = ?",
                (*fields.values(), receipt_id),
            )
            con.commit()

    def delete(self, receipt_id: str):
        with db_connection() as con:
            con.execute(
                "DELETE FROM receipts WHERE id = ?",
                (receipt_id,),
            )
            con.commit()

    def find_by_hash(self, sha256: str):
        with db_connection() as con:
            return con.execute(
                "SELECT id FROM receipts WHERE sha256 = ? LIMIT 1",
                (sha256,),
            ).fetchone()


class SQLiteMappingStorage:
    def __init__(self):
        _init_sqlite_db()

    def get(self, store_org: str, article_number: str):
        with db_connection() as con:
            return con.execute(
                """
                SELECT *
                FROM mappings
                WHERE store_org = ?
                  AND article_number = ?
                """,
                (store_org, article_number),
            ).fetchone()

    def save(
        self,
        store_org: str,
        article_number: str,
        grocy_product_id: int,
        grocy_product_name: str,
    ):
        with db_connection() as con:
            con.execute(
                """
                INSERT OR REPLACE INTO mappings (
                    store_org,
                    article_number,
                    grocy_product_id,
                    grocy_product_name,
                    created_at
                )
                VALUES (?, ?, ?, ?, datetime('now'))
                """,
                (
                    store_org,
                    article_number,
                    grocy_product_id,
                    grocy_product_name,
                ),
            )
            con.commit()

    def delete(self, store_org: str, article_number: str):
        with db_connection() as con:
            con.execute(
                """
                DELETE FROM mappings
                WHERE store_org = ?
                  AND article_number = ?
                """,
                (store_org, article_number),
            )
            con.commit()


def create_receipt_storage(storage_type: str):
    if storage_type == "sqlite":
        return SQLiteReceiptStorage()

    if storage_type == "none":
        return MemoryReceiptStorage()

    raise ValueError(f"Unsupported receipt storage: {storage_type}")


def create_mapping_storage(storage_type: str):
    if storage_type == "sqlite":
        return SQLiteMappingStorage()

    if storage_type == "none":
        return NullMappingStorage()

    raise ValueError(f"Unsupported mapping storage: {storage_type}")



def create_alias_storage(storage_type: str):
    if storage_type == "sqlite":
        return SQLiteAliasStorage()

    if storage_type == "none":
        return NullAliasStorage()

    raise ValueError(f"Unsupported alias storage: {storage_type}")


class MemoryReceiptStorage:
    def __init__(self):
        self._receipts = {}

    def get(self, receipt_id: str):
        return self._receipts.get(receipt_id)

    def list_recent(self, limit: int = 20):
        receipts = sorted(
            self._receipts.values(),
            key=lambda receipt: receipt["created_at"],
            reverse=True,
        )

        return receipts[:limit]

    def save(self, receipt):
        self._receipts[receipt["id"]] = dict(receipt)

    def update(self, receipt_id: str, **fields):
        receipt = self._receipts.get(receipt_id)

        if receipt is None:
            return

        receipt.update(fields)

    def delete(self, receipt_id: str):
        self._receipts.pop(receipt_id, None)

    def find_by_hash(self, sha256: str):
        for receipt in self._receipts.values():
            if receipt["sha256"] == sha256:
                return receipt

        return None


class SQLiteAliasStorage:
    def __init__(self):
        _init_sqlite_db()

    def get(self, store_org: str, normalized_description: str):
        with db_connection() as con:
            return con.execute(
                """
                SELECT *
                FROM aliases
                WHERE store_org = ?
                  AND normalized_description = ?
                """,
                (store_org, normalized_description),
            ).fetchone()

    def save(
        self,
        store_org: str,
        normalized_description: str,
        grocy_product_id: int | None,
        grocy_product_name: str,
        ignored: bool = False,
    ):
        with db_connection() as con:
            con.execute(
                """
                INSERT OR REPLACE INTO aliases (
                    store_org,
                    normalized_description,
                    grocy_product_id,
                    grocy_product_name,
                    ignored,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, datetime('now'))
                """,
                (
                    store_org,
                    normalized_description,
                    grocy_product_id,
                    grocy_product_name,
                    int(ignored),
                ),
            )
            con.commit()

    def delete(self, store_org: str, normalized_description: str):
        with db_connection() as con:
            con.execute(
                """
                DELETE FROM aliases
                WHERE store_org = ?
                  AND normalized_description = ?
                """,
                (store_org, normalized_description),
            )
            con.commit()


class NullAliasStorage:
    def get(self, store_org: str, normalized_description: str):
        return None

    def save(
        self,
        store_org: str,
        normalized_description: str,
        grocy_product_id: int | None,
        grocy_product_name: str,
        ignored: bool = False,
    ):
        pass

    def delete(self, store_org: str, normalized_description: str):
        pass


class NullMappingStorage:
    def get(self, store_org: str, article_number: str):
        return None

    def save(
        self,
        store_org: str,
        article_number: str,
        grocy_product_id: int,
        grocy_product_name: str,
    ):
        pass

    def delete(self, store_org: str, article_number: str):
        pass
