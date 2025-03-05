from PIL import Image, ImageDraw
import os

def create_favicon():
    # Create base image with solid background
    size = 512
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Use solid blue color instead of gradient for better visibility
    background_color = (37, 99, 235)  # #2563EB

    # Draw rounded square
    radius = size // 8
    draw.rounded_rectangle([(0, 0), (size-1, size-1)], radius=radius, fill=background_color)

    # Draw a bolder, simpler video camera icon
    icon_color = (255, 255, 255)  # White

    # Make the icon larger and bolder
    icon_margin = size // 4
    icon_width = size // 1.8
    icon_height = size // 2.2

    # Camera body - more rectangular for better visibility
    camera_body = [
        (icon_margin, size//2 - icon_height//2),  # Top left
        (icon_margin + icon_width, size//2 - icon_height//2),  # Top right
        (icon_margin + icon_width, size//2 + icon_height//2),  # Bottom right
        (icon_margin, size//2 + icon_height//2),  # Bottom left
    ]
    draw.polygon(camera_body, fill=icon_color)

    # Larger lens for better visibility
    lens_center = (icon_margin + icon_width//4, size//2)
    lens_size = icon_height//2.5
    draw.ellipse([
        (lens_center[0] - lens_size, lens_center[1] - lens_size),
        (lens_center[0] + lens_size, lens_center[1] + lens_size)
    ], fill=icon_color)

    # Save in different sizes
    sizes = {
        16: 'favicon-16x16.png',
        32: 'favicon-32x32.png',
        180: 'apple-touch-icon.png',
        192: 'android-chrome-192x192.png',
        512: 'android-chrome-512x512.png'
    }

    favicon_dir = 'static/favicon'
    os.makedirs(favicon_dir, exist_ok=True)

    for size, filename in sizes.items():
        resized = img.resize((size, size), Image.Resampling.LANCZOS)
        resized.save(os.path.join(favicon_dir, filename))

    # For ICO file, create a special version optimized for 16x16 and 32x32
    ico_img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    ico_draw = ImageDraw.Draw(ico_img)

    # Simpler shapes for small sizes
    ico_draw.rounded_rectangle([(0, 0), (size-1, size-1)], radius=radius, fill=background_color)

    # Simplified camera shape for small sizes
    simple_camera = [
        (size//3, size//3),  # Top left
        (2*size//3, size//3),  # Top right
        (2*size//3, 2*size//3),  # Bottom right
        (size//3, 2*size//3),  # Bottom left
    ]
    ico_draw.polygon(simple_camera, fill=icon_color)

    # Simplified lens
    simple_lens_center = (size//2.2, size//2)
    simple_lens_size = size//6
    ico_draw.ellipse([
        (simple_lens_center[0] - simple_lens_size, simple_lens_center[1] - simple_lens_size),
        (simple_lens_center[0] + simple_lens_size, simple_lens_center[1] + simple_lens_size)
    ], fill=icon_color)

    # Save ICO with special small size optimization
    ico_img.resize((32, 32), Image.Resampling.LANCZOS).save(
        os.path.join(favicon_dir, 'favicon.ico')
    )

if __name__ == '__main__':
    create_favicon()