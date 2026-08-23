from PIL import Image, ImageDraw
import os

def create_icon():
    base = Image.new("RGBA", (256, 256), (255, 255, 255, 255))
    draw = ImageDraw.Draw(base)

    m = 38
    draw.rectangle([m, 64, 256 - m, 192], fill=(0, 0, 0, 255))
    im = 90
    draw.rectangle([im, 96, 256 - im, 160], fill=(255, 255, 255, 255))

    sizes = [16, 32, 48, 64, 128, 256]
    resized = []
    for s in sizes:
        resized.append(base.resize((s, s), Image.Resampling.LANCZOS))

    icon_path = os.path.join(os.path.dirname(__file__), "assets", "duAI.ico")
    resized[0].save(
        icon_path,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=resized[1:],
    )
    print(f"ICON: {os.path.getsize(icon_path)} bytes")

    png_path = os.path.join(os.path.dirname(__file__), "assets", "duAI.png")
    base.save(png_path, format="PNG")
    print(f"PNG: {os.path.getsize(png_path)} bytes")

if __name__ == "__main__":
    create_icon()
