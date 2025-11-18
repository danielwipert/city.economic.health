from PIL import Image, ImageDraw, ImageFont
import os

def create_city_card(city_name, grade, metrics_dict, output_path):
    """
    Create a professional city economic grade card
    
    city_name: "New York" 
    grade: "A+"
    metrics_dict: {"Employment Score": 85, "Housing Score": 72, ...}
    """
    
    # Canvas setup - LinkedIn square
    width, height = 1080, 1080
    
    # HBR-inspired colors
    background = '#f8f7f5'  # Off-white
    primary_text = '#1a1f3a'  # Deep navy
    accent_color = '#8b2635'  # Burgundy
    secondary_text = '#6b6b6b'  # Warm grey
    
    # Create canvas
    img = Image.new('RGB', (width, height), background)
    draw = ImageDraw.Draw(img)
    
    # Load fonts (we'll start with default, then upgrade)
    try:
        # Try to load nice fonts
        font_city = ImageFont.truetype("arial.ttf", 72)
        font_grade = ImageFont.truetype("arialbd.ttf", 180)
        font_label = ImageFont.truetype("arial.ttf", 28)
        font_metric = ImageFont.truetype("arialbd.ttf", 36)
    except:
        # Fallback to default
        font_city = ImageFont.load_default()
        font_grade = ImageFont.load_default()
        font_label = ImageFont.load_default()
        font_metric = ImageFont.load_default()
    
    # Layout with lots of whitespace
    # Top: City name
    draw.text((90, 90), city_name.upper(), fill=primary_text, font=font_city)
    
    # Thin line under city name
    draw.rectangle([(90, 200), (990, 205)], fill=secondary_text)
    
    # Big grade in center
    draw.text((540, 380), grade, fill=accent_color, font=font_grade, anchor="mm")
    
    # Bottom: Key metrics
    y_position = 700
    draw.text((90, y_position), "ECONOMIC HEALTH INDEX", fill=secondary_text, font=font_label)
    
    # Save
    img.save(output_path, quality=95)
    print(f"✓ Created: {output_path}")

# Test it
create_city_card(
    city_name="New York",
    grade="A+",
    metrics_dict={},
    output_path="test_card.png"
)