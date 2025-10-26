from PIL import Image

from draw_stream.artistry.image_to_canvas import ImageToCanvas


def test_image_to_canvas_converts_colors() -> None:
    image = Image.new("RGB", (4, 4), "#000000")
    for y in range(2):
        for x in range(2):
            image.putpixel((x, y), (255, 0, 0))
    builder = ImageToCanvas()
    document = builder.build(image, caption="All for you")
    assert document.canvas.w == document.canvas.h == 96
    assert document.steps
    assert any(step.color == "#FF0000" for step in document.steps if hasattr(step, "color"))
