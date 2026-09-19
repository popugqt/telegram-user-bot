from pathlib import Path

import pytest

from bot.services.workspace import WorkspaceService


def test_workspace_is_topic_specific(tmp_path: Path) -> None:
	service = WorkspaceService(tmp_path)

	first = service.get(-100, None)
	second = service.get(-100, 123)

	assert first.host_path != second.host_path
	assert first.container_path != second.container_path


def test_validate_filename(tmp_path: Path) -> None:
	service = WorkspaceService(tmp_path)

	assert service.validate_filename("app.py") == "app.py"

	with pytest.raises(ValueError):
		service.validate_filename("../app.py")
