from dataclasses import dataclass
from typing import Iterable


LANGUAGES = {
	"python": "py",
	"py": "py",
	"node": "js",
	"nodejs": "js",
	"javascript": "js",
	"js": "js",
	"cpp": "cpp",
	"cxx": "cpp",
	"c++": "cpp",
	"java": "java",
	"brainfuck": "bf",
	"bf": "bf",
}

LANGUAGE_COMMANDS = list(LANGUAGES)


@dataclass(slots=True, frozen=True)
class CodeRequest:
	language: str
	extension: str
	filename: str | None
	code: str


def _entity_type_name(entity: object) -> str:
	entity_type = getattr(entity, "type", None)
	if entity_type is None:
		return ""

	values = (
		getattr(entity_type, "name", None),
		getattr(entity_type, "value", None),
		str(entity_type),
	)

	return " ".join(
		str(value).lower()
		for value in values
		if value is not None
	)


def _is_pre_entity(entity: object) -> bool:
	value = _entity_type_name(entity)
	return (
		value == "pre"
		or "messageentitytype.pre" in value
		or value.endswith(".pre")
	)


def _slice_utf16(text: str, offset: int, length: int) -> str:
	start = offset
	end = offset + length
	position = 0
	result: list[str] = []

	for character in text:
		units = 2 if ord(character) > 0xFFFF else 1
		next_position = position + units

		if next_position > start and position < end:
			result.append(character)

		position = next_position
		if position >= end:
			break

	return "".join(result)


def _extract_entity_code(
	text: str,
	entities: Iterable[object] | None,
) -> str | None:
	if not text or not entities:
		return None

	for entity in entities:
		if not _is_pre_entity(entity):
			continue

		offset = getattr(entity, "offset", None)
		length = getattr(entity, "length", None)
		if offset is None or length is None:
			continue

		code = _slice_utf16(text, int(offset), int(length)).strip("\n")
		if code:
			return code

	return None


def _extract_fenced_code(text: str) -> str | None:
	start = text.find("```")
	if start == -1:
		return None

	content_start = start + 3
	newline = text.find("\n", content_start)
	if newline == -1:
		return None

	end = text.find("```", newline + 1)
	if end == -1:
		return None

	return text[newline + 1:end].strip("\n")


def _extract_code(
	text: str,
	entities: Iterable[object] | None = None,
) -> str | None:
	code = _extract_fenced_code(text)
	if code is not None:
		return code

	return _extract_entity_code(text, entities)


def parse_code_request(
	text: str,
	entities: Iterable[object] | None = None,
) -> CodeRequest:
	text = text.strip("\n")
	if not text:
		raise ValueError("Пустая команда")

	first_line, _, _ = text.partition("\n")
	parts = first_line.strip().split(maxsplit=1)

	if not parts or not parts[0].startswith("."):
		raise ValueError("Некорректная команда языка")

	language = parts[0][1:].lower()
	if not language or any(
		character not in "abcdefghijklmnopqrstuvwxyz0123456789_+-"
		for character in language
	):
		raise ValueError("Некорректная команда языка")

	extension = LANGUAGES.get(language)
	if extension is None:
		raise ValueError(f"Язык {language} не поддерживается")

	filename = parts[1].strip() if len(parts) == 2 else None
	if filename and any(character.isspace() for character in filename):
		filename = filename.split()[0]

	code = _extract_code(text, entities) or ""

	return CodeRequest(
		language=language,
		extension=extension,
		filename=filename,
		code=code,
	)


def extract_code_block(
	text: str | None,
	entities: Iterable[object] | None = None,
) -> str | None:
	if not text:
		return None

	return _extract_code(text, entities)


__all__ = [
	"CodeRequest",
	"LANGUAGES",
	"LANGUAGE_COMMANDS",
	"extract_code_block",
	"parse_code_request",
]
