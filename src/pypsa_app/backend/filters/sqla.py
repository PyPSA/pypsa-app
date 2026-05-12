"""Translate a FilterAst into a SQLAlchemy boolean expression."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import and_, false, not_, or_, select, true

from pypsa_app.backend.filters.ast import (
    AndNode,
    FilterAst,
    FilterAstAdapter,
    InNode,
    NotNode,
    OrNode,
    TextNode,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy import ColumnElement, Select
    from sqlalchemy.orm import InstrumentedAttribute, Session


class FilterError(ValueError):
    """Raised for unknown fields, bad values, or malformed AST nodes.

    Routes catch this and translate to HTTP 422.
    """


@dataclass(frozen=True)
class FieldSpec:
    """Maps a filter field name to its SQL column and string-to-type coercer."""

    column: InstrumentedAttribute[Any]
    coerce: Callable[[str], Any]


FieldMap = dict[str, FieldSpec]


def enum_coercer[E: enum.Enum](cls: type[E]) -> Callable[[str], E]:
    """Return a case-insensitive string-to-enum coercer."""

    def coerce(s: str) -> E:
        target = s.casefold()
        for member in cls:
            if str(member.value).casefold() == target:
                return member
        msg = f"{s!r} is not a valid {cls.__name__}"
        raise ValueError(msg)

    return coerce


def name_to_id[M](
    db: Session, model: type[M], name_attr: str, label: str
) -> Callable[[str], Any]:
    """Return a coercer that resolves `model.<name_attr>` to its `id`."""

    def coerce(s: str) -> Any:
        obj = db.scalars(select(model).where(getattr(model, name_attr) == s)).first()
        if obj is None:
            msg = f"Unknown {label}: {s}"
            raise ValueError(msg)
        return obj.id

    return coerce


def _in_to_sqla(ast: InNode, field_map: FieldMap) -> ColumnElement[bool]:
    """Translate an InNode to a SQL IN clause. Empty values return FALSE."""
    spec = field_map.get(ast.field)
    if spec is None:
        msg = f"Unknown filter field: {ast.field!r}"
        raise FilterError(msg)
    try:
        coerced = [spec.coerce(v) for v in ast.values]
    except ValueError as e:
        msg = f"Invalid value for filter {ast.field!r}: {e}"
        raise FilterError(msg) from None
    if not coerced:
        return false()
    return spec.column.in_(coerced)


def _escape_like(value: str) -> str:
    r"""Escape SQL LIKE wildcards. Backslash is the escape char (set in `escape=`)."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _text_to_sqla(
    ast: TextNode,
    text_fields: tuple[InstrumentedAttribute[Any], ...],
) -> ColumnElement[bool]:
    """Translate a TextNode to ILIKE across all text_fields, OR-joined."""
    if not text_fields:
        msg = "text search not supported here"
        raise FilterError(msg)
    pattern = f"%{_escape_like(ast.value)}%"
    return or_(*(f.ilike(pattern, escape="\\") for f in text_fields))


def to_sqla(
    ast: FilterAst,
    field_map: FieldMap,
    text_fields: tuple[InstrumentedAttribute[Any], ...] = (),
) -> ColumnElement[bool]:
    """Recursively translate a FilterAst into a SQLAlchemy boolean expression.

    Empty AND = TRUE, empty OR = FALSE. Pass text_fields to enable
    free-text search. Empty tuple rejects TextNode leaves.
    """
    if isinstance(ast, InNode):
        return _in_to_sqla(ast, field_map)
    if isinstance(ast, TextNode):
        return _text_to_sqla(ast, text_fields)
    if isinstance(ast, AndNode):
        return (
            and_(*(to_sqla(c, field_map, text_fields) for c in ast.children))
            if ast.children
            else true()
        )
    if isinstance(ast, OrNode):
        return (
            or_(*(to_sqla(c, field_map, text_fields) for c in ast.children))
            if ast.children
            else false()
        )
    if isinstance(ast, NotNode):
        return not_(to_sqla(ast.child, field_map, text_fields))
    msg = f"Unknown AST node type: {type(ast).__name__}"
    raise FilterError(msg)


def resolve_filter_ast(filter_q: str | None) -> FilterAst:
    """Parse a JSON filter string into a FilterAst. None means no filter."""
    if filter_q is None:
        return AndNode(children=[])
    try:
        return FilterAstAdapter.validate_json(filter_q)
    except ValidationError as e:
        raise HTTPException(422, f"Invalid filter_q: {e}") from None


def apply_filter_to_query(
    query: Select,
    filter_q: str | None,
    field_map: FieldMap,
    text_fields: tuple[InstrumentedAttribute[Any], ...] = (),
) -> Select:
    """Parse and apply a JSON filter to a query. Raises 422 on invalid input."""
    ast = resolve_filter_ast(filter_q)
    try:
        return query.filter(to_sqla(ast, field_map, text_fields))
    except FilterError as e:
        raise HTTPException(422, str(e)) from None
