from __future__ import annotations

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
        grocy_product_id: int,
        grocy_product_name: str,
    ):
        ...

    def delete(self, store_org: str, normalized_description: str):
        ...


def db():
    os.makedirs(DATA_DIR, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def _init_sqlite_db():
    con = db()
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
    """)
    con.commit()
    con.close()




class SQLiteReceiptStorage:
    def __init__(self):
        _init_sqlite_db()

    def get(self, receipt_id: str):
        con = db()
        try:
            return con.execute(
                "SELECT * FROM receipts WHERE id = ?",
                (receipt_id,),
            ).fetchone()
        finally:
            con.close()

    def list_recent(self, limit: int = 20):
        con = db()
        try:
            return con.execute(
                """
                SELECT id, filename, metadata_json, status, created_at
                FROM receipts
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        finally:
            con.close()

    def save(self, receipt):
        con = db()
        try:
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
        finally:
            con.close()

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

        con = db()
        try:
            con.execute(
                f"UPDATE receipts SET {assignments} WHERE id = ?",
                (*fields.values(), receipt_id),
            )
            con.commit()
        finally:
            con.close()

    def delete(self, receipt_id: str):
        con = db()
        try:
            con.execute(
                "DELETE FROM receipts WHERE id = ?",
                (receipt_id,),
            )
            con.commit()
        finally:
            con.close()

    def find_by_hash(self, sha256: str):
        con = db()
        try:
            return con.execute(
                "SELECT id FROM receipts WHERE sha256 = ? LIMIT 1",
                (sha256,),
            ).fetchone()
        finally:
            con.close()


class SQLiteMappingStorage:
    def __init__(self):
        _init_sqlite_db()

    def get(self, store_org: str, article_number: str):
        con = db()
        try:
            return con.execute(
                """
                SELECT *
                FROM mappings
                WHERE store_org = ?
                  AND article_number = ?
                """,
                (store_org, article_number),
            ).fetchone()
        finally:
            con.close()

    def save(
        self,
        store_org: str,
        article_number: str,
        grocy_product_id: int,
        grocy_product_name: str,
    ):
        con = db()
        try:
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
        finally:
            con.close()

    def delete(self, store_org: str, article_number: str):
        con = db()
        try:
            con.execute(
                """
                DELETE FROM mappings
                WHERE store_org = ?
                  AND article_number = ?
                """,
                (store_org, article_number),
            )
            con.commit()
        finally:
            con.close()


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
