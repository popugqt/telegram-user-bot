import time


_started_at: float | None = None


def set_started_at() -> None:
	global _started_at
	_started_at = time.time()


def get_started_at() -> float | None:
	return _started_at


def get_uptime() -> int:
	if _started_at is None:
		return 0

	return max(0, int(time.time() - _started_at))


__all__ = ["set_started_at", "get_started_at", "get_uptime"]
