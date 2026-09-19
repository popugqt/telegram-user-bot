from bot.services.code_parser import extract_code_block, parse_code_request


def test_parse_python_code() -> None:
	request = parse_code_request(
		".python test\n```python\nprint('hello')\n```"
	)

	assert request.extension == "py"
	assert request.filename == "test"
	assert request.code == "print('hello')"


def test_parse_without_code_block() -> None:
	request = parse_code_request(".cpp app")

	assert request.extension == "cpp"
	assert request.filename == "app"
	assert request.code == ""


def test_extract_code_from_reply() -> None:
	assert extract_code_block("text\n```java\nclass Main {}\n```") == "class Main {}"


def test_parse_brainfuck_alias() -> None:
	request = parse_code_request(".bf\n```brainfuck\n+++++[>+++++<-]>.\n```")

	assert request.language == "bf"
	assert request.extension == "bf"
	assert request.code == "+++++[>+++++<-]>."
