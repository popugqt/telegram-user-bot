import logging
from pathlib import Path

from PIL import Image, ImageStat
import pytesseract
from pytesseract import Output

from bot.services.image import ImageService


logger = logging.getLogger(__name__)


OCR_LANGUAGE_ALIASES = {
	"ru": "rus",
	"ру": "rus",
	"eng": "eng",
	"англ": "eng",
	"ру/англ": "rus+eng",
	"ru/eng": "rus+eng",
	"ru+eng": "rus+eng",
	"rus+eng": "rus+eng",
}


class OCRService:
	def __init__(
		self,
		languages: str = "rus+eng",
	) -> None:
		self.languages = languages

	def recognize(self, image: Image.Image) -> str:
		gray = image.convert("L")
		brightness = ImageStat.Stat(gray).mean[0]

		candidates = [
			(ImageService.prepare_for_ocr(image, scale=2), 6),
			(ImageService.prepare_for_ocr(image, scale=2), 11),
			(ImageService.prepare_for_ocr(image, scale=2, threshold=170), 6),
			(ImageService.prepare_for_ocr(image, scale=2, threshold=170), 11),
		]

		if brightness < 128:
			candidates.append(
				(ImageService.prepare_for_ocr(
					image,
					scale=2,
					threshold=170,
					invert=True,
				), 6)
			)

		best_text = ""
		best_score = float("-inf")

		for prepared, psm in candidates:
			try:
				text, confidence = self._run(prepared, psm)
			except (pytesseract.TesseractError, RuntimeError):
				logger.exception("Tesseract failed with psm=%s", psm)
				continue

			if not text:
				continue

			score = confidence + min(len(text), 500) / 500
			if score > best_score:
				best_score = score
				best_text = text

		logger.debug(
			"OCR completed, recognized %d characters, score %.2f",
			len(best_text),
			best_score,
		)

		return best_text.strip()

	def _run(self, image: Image.Image, psm: int) -> tuple[str, float]:
		config = (
			f"--oem 1 --psm {psm} "
			"-c preserve_interword_spaces=1"
		)

		data = pytesseract.image_to_data(
			image,
			lang=self.languages,
			config=config,
			output_type=Output.DICT,
			timeout=20,
		)

		parts: dict[tuple[int, int, int], list[str]] = {}
		confidences: list[float] = []

		texts = data.get("text", [])
		blocks = data.get("block_num", [])
		paragraphs = data.get("par_num", [])
		lines = data.get("line_num", [])
		conf_values = data.get("conf", [])

		for index, value in enumerate(texts):
			value = str(value).strip()
			if not value:
				continue

			key = (
				int(blocks[index]),
				int(paragraphs[index]),
				int(lines[index]),
			)
			parts.setdefault(key, []).append(value)

			try:
				confidence = float(conf_values[index])
			except (TypeError, ValueError):
				continue

			if confidence >= 0:
				confidences.append(confidence)

		text = "\n".join(
			" ".join(values)
			for _, values in sorted(parts.items())
		)

		confidence = (
			sum(confidences) / len(confidences)
			if confidences
			else 0.0
		)

		return text, confidence

	def recognize_file(self, path: str | Path) -> str:
		with Image.open(path) as image:
			return self.recognize(image)


def normalize_languages(value: str | None) -> str:
	if value is None or not value.strip():
		return "rus+eng"

	value = value.strip().lower()
	return OCR_LANGUAGE_ALIASES.get(value, value)


__all__ = ["OCRService", "normalize_languages"]
