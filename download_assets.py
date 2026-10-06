import os
import re
import requests
from urllib.parse import urljoin, urlparse

VENDOR_DIR = r"d:\The Project\statathon1.1\static\vendor"

ASSETS = {
    "css": [
        "https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css",
        "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css",
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap"
    ],
    "js": [
        "https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js",
        "https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js",
        "https://d3js.org/d3.v7.min.js"
    ],
    "img": [
        "https://upload.wikimedia.org/wikipedia/commons/5/55/Emblem_of_India.svg",
        "https://gc.mic.gov.in/statathon-2025.png"
    ]
}

def download_file(url, out_path):
    print(f"Downloading {url} to {out_path}...")
    headers = {'User-Agent': 'Mozilla/5.0'}
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'wb') as f:
        f.write(r.content)
    return r.text

def process_css(css_text, base_url, out_dir):
    urls = re.findall(r'url\((.*?)\)', css_text)
    for u in urls:
        u_clean = u.strip("'\"")
        if u_clean.startswith('data:'): continue
        abs_url = urljoin(base_url, u_clean)
        
        parsed = urlparse(abs_url)
        filename = os.path.basename(parsed.path)
        
        # Save to fonts directory
        font_out_path = os.path.join(out_dir, "fonts", filename)
        download_file(abs_url, font_out_path)
        
        # Replace in CSS
        css_text = css_text.replace(u, f"'fonts/{filename}'")
    return css_text

os.makedirs(VENDOR_DIR, exist_ok=True)

# CSS
css_dir = os.path.join(VENDOR_DIR, "css")
os.makedirs(css_dir, exist_ok=True)
for url in ASSETS["css"]:
    if "Inter" in url:
        name = "inter.css"
    else:
        name = os.path.basename(urlparse(url).path)
    
    out_path = os.path.join(css_dir, name)
    text = download_file(url, out_path)
    if "font-awesome" in url or "fonts.googleapis" in url:
        processed_css = process_css(text, url, css_dir)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(processed_css)

# JS
js_dir = os.path.join(VENDOR_DIR, "js")
os.makedirs(js_dir, exist_ok=True)
for url in ASSETS["js"]:
    name = os.path.basename(urlparse(url).path)
    out_path = os.path.join(js_dir, name)
    download_file(url, out_path)

# IMG
img_dir = os.path.join(VENDOR_DIR, "img")
os.makedirs(img_dir, exist_ok=True)
for url in ASSETS["img"]:
    name = os.path.basename(urlparse(url).path)
    out_path = os.path.join(img_dir, name)
    download_file(url, out_path)

print("All assets downloaded successfully.")
