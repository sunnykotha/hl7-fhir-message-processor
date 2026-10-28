from dataclasses import dataclass


class HL7ParseError(ValueError):
    """Raised when an HL7 message has an invalid structure."""


def decode_escapes(
    value: str,
    encoding_characters: str,
    field_separator: str = "|",
) -> str:
    """Decode standard HL7 delimiter and formatting escapes."""
    if len(encoding_characters) < 4:
        return value

    component, repetition, escape, subcomponent = encoding_characters[:4]
    replacements = {
        "F": field_separator,
        "S": component,
        "R": repetition,
        "T": subcomponent,
        "E": escape,
        ".br": "\n",
    }

    result = []
    index = 0

    while index < len(value):
        if value[index] != escape:
            result.append(value[index])
            index += 1
            continue

        end = value.find(escape, index + 1)
        if end == -1:
            result.append(value[index:])
            break

        code = value[index + 1:end]
        if code in replacements:
            result.append(replacements[code])
        else:
            result.append(value[index:end + 1])

        index = end + 1

    return "".join(result)

@dataclass(frozen=True)
class Segment:
    name: str
    raw: str
    field_separator: str
    encoding_characters: str

    def field(self, number: int) -> str:
        """Return a one-based HL7 field, preserving empty fields."""
        if number < 1:
            raise ValueError("HL7 field numbers start at 1")

        parts = self.raw.split(self.field_separator)

        if self.name == "MSH":
            if number == 1:
                return self.field_separator
            index = number - 1
        else:
            index = number

        if index >= len(parts):
            return ""

        return parts[index]

    def repetitions(self, number: int) -> tuple[str, ...]:
        """Return the repetitions within a field, without decoding escapes."""
        if number == 1 and self.name == "MSH":
            return (self.field_separator,)

        value = self.field(number)
        separator = self.encoding_characters[1]
        return tuple(value.split(separator))

    def components(self, number: int, repetition_number: int = 1) -> tuple[str, ...]:
        """Return one-based repetition components, preserving empty components."""
        repetitions = self.repetitions(number)

        if repetition_number < 1 or repetition_number > len(repetitions):
            raise ValueError("Repetition number is out of range")

        separator = self.encoding_characters[0]
        return tuple(repetitions[repetition_number - 1].split(separator))

    def subcomponents(
        self,
        number: int,
        component_number: int = 1,
        repetition_number: int = 1,
    ) -> tuple[str, ...]:
        """Return subcomponents of a one-based component and repetition."""
        components = self.components(number, repetition_number)

        if component_number < 1 or component_number > len(components):
            raise ValueError("Component number is out of range")

        separator = self.encoding_characters[3]
        return tuple(components[component_number - 1].split(separator))

    def decoded_field(self, number: int) -> str:
        """Return a field with supported HL7 escape sequences decoded."""
        return decode_escapes(self.field(number), self.encoding_characters, self.field_separator)

    def decoded_components(
        self, number: int, repetition_number: int = 1
    ) -> tuple[str, ...]:
        """Return decoded components for one repetition."""
        return tuple(
            decode_escapes(value, self.encoding_characters, self.field_separator)
            for value in self.components(number, repetition_number)
        )


@dataclass(frozen=True)
class HL7Message:
    segments: tuple[Segment, ...]
    field_separator: str
    encoding_characters: str

    @classmethod
    def parse(
        cls,
        text: str | bytes,
        encoding: str = "utf-8",
    ) -> "HL7Message":
        """Decode message bytes when needed, then parse HL7 segments."""
        if isinstance(text, bytes):
            try:
                text = text.decode(encoding)
            except (LookupError, UnicodeDecodeError) as exc:
                raise HL7ParseError(
                    f"Message cannot be decoded using {encoding!r}"
                ) from exc

        if not isinstance(text, str) or not text.strip():
            raise HL7ParseError("Message must not be empty")

        lines = [line for line in text.splitlines() if line.strip()]

        if not lines or not lines[0].startswith("MSH"):
            raise HL7ParseError("The first segment must be MSH")

        msh_line = lines[0]

        if len(msh_line) < 4:
            raise HL7ParseError("MSH does not declare a field separator")

        field_separator = msh_line[3]

        if field_separator.isalnum() or field_separator.isspace():
            raise HL7ParseError("Invalid MSH field separator")

        encoding_characters = msh_line[4:].split(field_separator)[0]

        if len(encoding_characters) < 4:
            raise HL7ParseError(
                "MSH-2 must declare at least four encoding characters"
            )

        if len(set(encoding_characters[:4])) != 4:
            raise HL7ParseError("HL7 encoding characters must be distinct")

        if field_separator in encoding_characters[:4]:
            raise HL7ParseError(
                "Field separator must differ from encoding characters"
            )

        segments = []

        for line in lines:
            if len(line) < 3:
                raise HL7ParseError(
                    "Segment name must contain three characters"
                )

            name = line[:3]

            if not (
                name.isascii()
                and name.isalnum()
                and name.upper() == name
            ):
                raise HL7ParseError(f"Invalid segment name: {name!r}")

            segments.append(
                Segment(
                    name=name,
                    raw=line,
                    field_separator=field_separator,
                    encoding_characters=encoding_characters,
                )
            )

        return cls(
            segments=tuple(segments),
            field_separator=field_separator,
            encoding_characters=encoding_characters,
        )

    def segments_named(self, name: str) -> tuple[Segment, ...]:
        """Return all matching segments in message order."""
        return tuple(s for s in self.segments if s.name == name)

    def first_segment(self, name: str) -> Segment | None:
        """Return the first matching segment, or None."""
        return next((s for s in self.segments if s.name == name), None)
