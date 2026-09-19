from PIL import Image, ImageFilter, ImageOps


class ImageService:
	@staticmethod
	def prepare_for_ocr(
		image: Image.Image,
		scale: int = 2,
		threshold: int | None = None,
		invert: bool = False,
	) -> Image.Image:
		image = image.convert("L")
		image = ImageOps.autocontrast(image)
		image = image.filter(ImageFilter.SHARPEN)

		if scale > 1:
			image = image.resize(
				(
					max(1, image.width * scale),
					max(1, image.height * scale),
				),
				Image.Resampling.LANCZOS,
			)

		if threshold is not None:
			image = image.point(
				lambda value: 255 if value >= threshold else 0,
				mode="1",
			)

		if invert:
			image = ImageOps.invert(image.convert("L"))

		return image


__all__ = ["ImageService"]
