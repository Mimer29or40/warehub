from __future__ import annotations

import json
import re
from dataclasses import MISSING, Field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Literal, Type, TypeVar, Union

__all__ = [
    "Encoder",
    "Decoder",
    "Table",
    "Database",
]

T = TypeVar("T")
JsonValue = Union[dict, list, str, int, float, bool, Literal[None]]


class Encoder:
    def __init__(self, obj_type: Type[T], encoder: Callable[[T], JsonValue]):
        self.obj_type = obj_type
        self.encoder = encoder

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(obj_type={self.obj_type.__name__})"

    def check(self, obj: Any) -> bool:
        """Check if object can be encoded"""
        return self.obj_type == obj.__class__

    def encode(self, obj: Any) -> dict[str, JsonValue]:
        """Encodes the python object into a JSON object"""
        return {
            "__type__": self.obj_type.__name__,
            "value": self.encoder(obj),
        }


class Decoder:
    def __init__(self, obj_type: Type[T], decoder: Callable[[JsonValue], T]):
        self.obj_type = obj_type
        self.decoder = decoder

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(obj_type={self.obj_type.__name__})"

    def check(self, obj: dict[str, JsonValue]) -> bool:
        """Check if object can be decoded"""
        return self.obj_type.__name__ == obj["__type__"]

    def decode(self, obj: dict[str, JsonValue]) -> Any:
        """Decodes the JSON object into a python object"""
        return self.decoder(obj["value"])


class TableEncoder(Encoder):
    def __init__(self):
        super().__init__(Table, asdict)

    def __hash__(self) -> int:
        return hash(Table)

    def check(self, obj: Any) -> bool:
        """Check if object can be encoded"""
        return isinstance(obj, Table)

    def encode(self, obj: Any) -> dict[str, JsonValue]:
        """Encodes the python object into a JSON object"""
        return {
            "__type__": obj.__class__.__name__,
            "value": self.encoder(obj),
        }


class TableDecoder(Decoder):
    def __init__(self):
        super().__init__(Table, lambda x: None)

    def __hash__(self) -> int:
        return hash(Table)

    @staticmethod
    def sub_types(_type: type) -> dict[str, type]:
        sub_types = {_type.__name__: _type}
        for sub in _type.__subclasses__():
            sub_types.update(TableDecoder.sub_types(sub))
        return sub_types

    def check(self, obj: dict[str, JsonValue]) -> bool:
        """Check if object can be decoded"""
        return obj["__type__"] in TableDecoder.sub_types(Table)

    def decode(self, obj: dict[str, JsonValue]) -> Any:
        """Decodes the JSON object into a python object"""
        return TableDecoder.sub_types(Table)[obj["__type__"]](**obj["value"])


class Comparison:
    def __init__(self, compare: Callable[[Table], bool]):
        self.compare = compare

    def __and__(self, other: Comparison):
        return Comparison(lambda e: self.compare(e) and other.compare(e))

    def __or__(self, other: Comparison):
        return Comparison(lambda e: self.compare(e) or other.compare(e))


class TableField(Field):
    # noinspection PyMissingConstructor
    def __init__(self, field: Field):
        for attr in Field.__slots__:
            setattr(self, attr, getattr(field, attr))

    @property
    def get_default(self) -> Any:
        if self.default_factory is MISSING:
            return self.default
        return self.default_factory()

    def __repr__(self) -> str:
        default = "MISSING" if self.get_default is MISSING else self.get_default
        return f"TableAttr(name={self.name}, type={self.type}, default={default})"

    def __lt__(self, other: Any):
        return Comparison(lambda e: getattr(e, self.name) < other)

    def __le__(self, other: Any):
        return Comparison(lambda e: getattr(e, self.name) <= other)

    def __eq__(self, other: Any):
        try:
            pattern = re.compile(other)
            return Comparison(
                lambda e: pattern.search(getattr(e, self.name)) is not None
            )
        except (re.error, TypeError):
            return Comparison(lambda e: getattr(e, self.name) == other)

    def __ne__(self, other: Any):
        try:
            pattern = re.compile(other)
            return Comparison(lambda e: pattern.search(getattr(e, self.name)) is None)
        except (re.error, TypeError):
            return Comparison(lambda e: getattr(e, self.name) != other)

    def __gt__(self, other: Any):
        return Comparison(lambda e: getattr(e, self.name) > other)

    def __ge__(self, other: Any):
        return Comparison(lambda e: getattr(e, self.name) >= other)


class MetaTable(type):
    def __getattribute__(self, name):
        if name != "__dataclass_fields__" and name in (
            dict := getattr(self, "__dataclass_fields__", {})
        ):
            return dict.setdefault(f"{name}_attr", TableField(dict[name]))
        return super().__getattribute__(name)


class Table(metaclass=MetaTable):
    @property
    def id(self):
        return self._id

    def __post_init__(self):
        self._id = -1

    def __eq__(self, other) -> bool:
        if self.__class__ == other.__class__:
            # Both objects are table entries
            if self.id == -1 and other.id == -1:
                # Both objects are not in database
                return super().__eq__(other)
            if self.id == other.id:
                # Both objects refer to same table entry
                return True
        return False


TableType = TypeVar("TableType", bound=Table)
ComparisonType = Union[Comparison, bool]


class Database:
    _file: Path = Path("data.json")
    _data: dict[str, Any] = None

    _encoders: dict[str, Encoder] = {}
    _decoders: dict[str, Decoder] = {}

    @classmethod
    def file(cls, new_file: Path = None) -> Path:
        if new_file is not None:
            cls._file = new_file
        return cls._file

    @classmethod
    def register_encoder(cls, encoder: Encoder) -> None:
        _type = encoder.obj_type.__name__
        if _type in cls._encoders:
            raise TypeError(f"Encoder for type '{_type}' already registered")
        cls._encoders[_type] = encoder

    @classmethod
    def register_decoder(cls, decoder: Decoder) -> None:
        _type = decoder.obj_type.__name__
        if _type in cls._decoders:
            raise TypeError(f"Decoder for type '{_type}' already registered")
        cls._decoders[_type] = decoder

    @classmethod
    def _encode(cls, obj: Any) -> dict[str, JsonValue]:
        found = [e for e in cls._encoders.values() if e.check(obj)]
        _len = len(found)
        if _len > 1:
            obj_type = obj.__class__.__name__
            TypeError(f"Multiple encoders found for {obj_type}: {found}")
        if _len == 1:
            return found[0].encode(obj)
        obj_type = obj.__class__.__name__
        raise TypeError(f"Object of type {obj_type} is not JSON serializable")

    @classmethod
    def _decode(cls, obj: dict[str, JsonValue]) -> Any:
        if "__type__" in obj:
            found = [d for d in cls._decoders.values() if d.check(obj)]
            _len = len(found)
            if _len > 1:
                obj_type = obj["__type__"]
                TypeError(f"Multiple decoders found for {obj_type}: {found}")
            if _len == 1:
                return found[0].decode(obj)
            obj_type = obj["__type__"]
            raise TypeError(f"Object of type {obj_type} is not JSON deserializable")
        return obj

    @classmethod
    def last_commit(cls) -> datetime:
        if cls._data is None:
            cls.rollback()
        return datetime.fromisoformat(cls._data["last_commit"])

    @classmethod
    def rollback(cls) -> None:
        try:
            cls._data = json.loads(cls._file.read_text(), object_hook=cls._decode)
        except (FileNotFoundError, json.decoder.JSONDecodeError):
            cls._data = {"last_commit": datetime.now()}

    @classmethod
    def commit(cls) -> bool:
        if cls._data is None:
            cls.rollback()

        previous_commit = (
            cls._data["last_commit"] if "last_commit" in cls._data else None
        )
        try:
            cls._data["last_commit"] = datetime.now()
            cls._file.write_text(json.dumps(cls._data, indent=2, default=cls._encode))
            return True
        except (IOError, Exception) as e:
            cls._data["last_commit"] = (
                datetime.now() if previous_commit is None else previous_commit
            )
            print(f"I/O error({e.errno}): {e.strerror}")
        return False

    @classmethod
    def get(
        cls, table: Type[TableType], where: ComparisonType = None
    ) -> tuple[TableType]:
        results: list[TableType] = []
        for id, entry in cls._get(table, where):
            entry._id = int(id)
            results.append(entry)
        return tuple(results)

    @classmethod
    def pop(
        cls, table: Type[TableType], where: ComparisonType = None
    ) -> tuple[TableType]:
        results: list[TableType] = []
        for id, table_entry in cls._get(table, where):
            results.append(table(**table_entry))
        return tuple(results)

    @classmethod
    def put(cls, table: Type[TableType], *entries: TableType):
        if cls._data is None:
            cls.rollback()

        table_name = table.__name__.lower()

        if table_name not in cls._data:
            cls._data[table_name] = {}

        table_data = cls._data[table_name]

        for entry in entries:
            if entry.id < 0:
                id = 0
                while str(id) in table_data:
                    id += 1
                entry._id = id
            table_data[str(entry.id)] = entry

    @classmethod
    def _get(
        cls, table: Type[TableType], where: ComparisonType = None
    ) -> list[tuple[str, TableType]]:
        if cls._data is None:
            cls.rollback()

        table_name = table.__name__.lower()
        if table_name not in cls._data:
            return []

        pre_check = where is None or (isinstance(where, bool) and where)

        results: list[tuple[str, TableType]] = []
        for id, table_entry in cls._data[table_name].items():
            if pre_check or where.compare(table_entry):
                results.append((id, table_entry))
        return results


for register, coder in {
    (
        Database.register_encoder,
        Encoder(datetime, lambda datetime: datetime.isoformat()),
    ),
    (
        Database.register_decoder,
        Decoder(datetime, lambda datetime_str: datetime.fromisoformat(datetime_str)),
    ),
    (Database.register_encoder, TableEncoder()),
    (Database.register_decoder, TableDecoder()),
}:
    try:
        register(coder)
    except KeyError:
        pass
