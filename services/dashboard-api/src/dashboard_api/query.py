from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class QueryBuilder:
    base_select: str
    base_count: str
    order_by: str
    where: list[str] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)

    def add_equal(self, column: str, name: str, value: Any) -> None:
        if value is None:
            return
        self.where.append(f"{column} = %({name})s")
        self.params[name] = value

    def add_gte(self, column: str, name: str, value: Any) -> None:
        if value is None:
            return
        self.where.append(f"{column} >= %({name})s")
        self.params[name] = value

    def add_lte(self, column: str, name: str, value: Any) -> None:
        if value is None:
            return
        self.where.append(f"{column} <= %({name})s")
        self.params[name] = value

    def add_search(self, columns: Iterable[str], name: str, value: str | None) -> None:
        if not value:
            return
        parts = [f"{column} ilike %({name})s" for column in columns]
        self.where.append("(" + " or ".join(parts) + ")")
        self.params[name] = f"%{value}%"

    def where_sql(self) -> str:
        if not self.where:
            return ""
        return " where " + " and ".join(self.where)

    def list_sql(self) -> str:
        return f"{self.base_select}{self.where_sql()} {self.order_by} limit %(limit)s offset %(offset)s"

    def count_sql(self) -> str:
        return f"{self.base_count}{self.where_sql()}"


def clamp_page_size(page_size: int, max_page_size: int) -> int:
    return min(max(page_size, 1), max_page_size)


def offset_for(page: int, page_size: int) -> int:
    return (max(page, 1) - 1) * page_size
