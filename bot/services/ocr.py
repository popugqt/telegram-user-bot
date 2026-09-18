import logging
from pathlib import Path

from PIL import Image
import pytesseract

from bot.services.image import ImageService


logger = logging.getLogger(__name__)


class OCRService:
    def __init__(
            self,
            languages: str = "rus",
    ) -> None:
        self.languages = languages

    def recognize(self, image: Image.Image) -> str:
        """Recognize text from an image."""
        image = ImageService.prepare_for_ocr(image)

        logger.debug("Starting OCR")

        text = pytesseract.image_to_string(
            image,
            lang=self.languages,
            config="--oem 1 --psm 11 -c preserve_interword_spaces=1",
        )

        logger.debug(
            "OCR completed, recognized %d characters",
            len(text),
        )

        return text.strip()

    def recognize_file(self, path: str | Path) -> str:
        with Image.open(path) as image:
            return self.recognize(image)
