from __future__ import annotations

from dataclasses import dataclass


class InvalidSidcError(ValueError):
    """Raised when a SIDC is malformed."""


@dataclass(frozen=True, slots=True)
class Sidc:
    """A validated fixed-width 20-digit Symbol Identification Code."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise InvalidSidcError("SIDC must be supplied as a string")
        if len(self.value) != 20 or not self.value.isascii() or not self.value.isdigit():
            raise InvalidSidcError("SIDC must contain exactly 20 ASCII digits")

    def __str__(self) -> str:
        return self.value

    @property
    def version(self) -> str:
        return self.value[0:2]

    @property
    def context(self) -> str:
        return self.value[2]

    @property
    def identity(self) -> str:
        return self.value[3]

    @property
    def symbol_set(self) -> str:
        return self.value[4:6]

    @property
    def status(self) -> str:
        return self.value[6]

    @property
    def hq_task_force_dummy(self) -> str:
        return self.value[7]

    @property
    def amplifier(self) -> str:
        return self.value[8:10]

    @property
    def entity(self) -> str:
        return self.value[10:16]

    @property
    def modifier_one(self) -> str:
        return self.value[16:18]

    @property
    def modifier_two(self) -> str:
        return self.value[18:20]

    def fields(self) -> dict[str, str]:
        return {
            "version": self.version,
            "context": self.context,
            "identity": self.identity,
            "symbol_set": self.symbol_set,
            "status": self.status,
            "hq_task_force_dummy": self.hq_task_force_dummy,
            "amplifier": self.amplifier,
            "entity": self.entity,
            "modifier_one": self.modifier_one,
            "modifier_two": self.modifier_two,
        }

