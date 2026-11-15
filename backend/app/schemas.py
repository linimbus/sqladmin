from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

DBKind = Literal["sqlite", "mysql", "postgresql", "mssql", "oracle"]


class ConnectionBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: DBKind
    host: Optional[str] = None
    port: Optional[int] = Field(default=None, ge=1, le=65535)
    username: Optional[str] = None
    password: Optional[str] = None
    database: Optional[str] = None
    sqlite_path: Optional[str] = None
    options: Dict[str, Any] = Field(default_factory=dict)
    read_only: bool = False

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("连接名称不能为空")
        return value


class ConnectionCreate(ConnectionBase):
    pass


class ConnectionUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    kind: Optional[DBKind] = None
    host: Optional[str] = None
    port: Optional[int] = Field(default=None, ge=1, le=65535)
    username: Optional[str] = None
    password: Optional[str] = None
    database: Optional[str] = None
    sqlite_path: Optional[str] = None
    options: Optional[Dict[str, Any]] = None
    read_only: Optional[bool] = None


class ConnectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    kind: str
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    database: Optional[str] = None
    sqlite_path: Optional[str] = None
    options: Dict[str, Any] = Field(default_factory=dict)
    read_only: bool = False
    has_password: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ConnectionTest(ConnectionBase):
    id: Optional[int] = None


class TestResult(BaseModel):
    ok: bool
    message: str
    version: Optional[str] = None
    latency_ms: Optional[float] = None


# ---------------------------------------------------------------------------
# Explorer
# ---------------------------------------------------------------------------


class CatalogOut(BaseModel):
    kind: str
    current_database: Optional[str] = None
    databases: List[str] = Field(default_factory=list)
    schemas: List[str] = Field(default_factory=list)
    namespace: str = "schema"  # database | schema


class TableObject(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    type: str = "table"
    schema_name: Optional[str] = Field(default=None, alias="schema")
    comment: Optional[str] = None
    row_estimate: Optional[int] = None


class TablesOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    database: Optional[str] = None
    schema_name: Optional[str] = Field(default=None, alias="schema")
    tables: List[TableObject] = Field(default_factory=list)
    views: List[TableObject] = Field(default_factory=list)


class ColumnInfo(BaseModel):
    name: str
    type: str
    nullable: bool = True
    default: Optional[str] = None
    primary_key: bool = False
    autoincrement: bool = False
    computed: bool = False
    comment: Optional[str] = None
    length: Optional[int] = None


class IndexInfo(BaseModel):
    name: str
    columns: List[str] = Field(default_factory=list)
    unique: bool = False


class ForeignKeyInfo(BaseModel):
    name: Optional[str] = None
    columns: List[str] = Field(default_factory=list)
    referred_table: Optional[str] = None
    referred_columns: List[str] = Field(default_factory=list)


class TableDetail(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    type: str = "table"
    database: Optional[str] = None
    schema_name: Optional[str] = Field(default=None, alias="schema")
    columns: List[ColumnInfo] = Field(default_factory=list)
    primary_key: List[str] = Field(default_factory=list)
    indexes: List[IndexInfo] = Field(default_factory=list)
    foreign_keys: List[ForeignKeyInfo] = Field(default_factory=list)
    ddl: Optional[str] = None


class RowColumn(BaseModel):
    name: str
    type: str
    nullable: bool = True


class RowsOut(BaseModel):
    columns: List[RowColumn] = Field(default_factory=list)
    rows: List[List[Any]] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 50
    primary_key: List[str] = Field(default_factory=list)
    duration_ms: float = 0


class RowMutation(BaseModel):
    values: Dict[str, Any] = Field(default_factory=dict)
    pk: Dict[str, Any] = Field(default_factory=dict)


class MutationResult(BaseModel):
    ok: bool = True
    affected: int = 0
    inserted: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------


class QueryRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    sql: str = Field(min_length=1)
    max_rows: int = Field(default=500, ge=1)
    database: Optional[str] = None
    schema_name: Optional[str] = Field(default=None, alias="schema")


class StatementResult(BaseModel):
    index: int
    statement: str
    type: str
    columns: List[RowColumn] = Field(default_factory=list)
    rows: List[List[Any]] = Field(default_factory=list)
    row_count: Optional[int] = None
    truncated: bool = False
    duration_ms: float = 0
    error: Optional[str] = None


class QueryResponse(BaseModel):
    ok: bool = True
    results: List[StatementResult] = Field(default_factory=list)
    duration_ms: float = 0
    error: Optional[str] = None
    read_only: bool = False


class OverviewOut(BaseModel):
    version: Optional[str] = None
    database: Optional[str] = None
    size_bytes: Optional[int] = None
    size_pretty: Optional[str] = None
    table_count: int = 0
    view_count: int = 0
    latency_ms: float = 0
