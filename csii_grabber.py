import argparse
import io
import math
from pathlib import Path

import cv2
import numpy as np
import requests
from PIL import Image
from scipy.ndimage import median_filter

# Configuration & Constants
Image.MAX_IMAGE_PIXELS = None
OSM_HEADERS = {'User-Agent': 'CS2-MapGenerator/1.0 (https://github.com/GoOcto/CSII-maps; paul@goocto.com)'}

CSII_CITY_METERS = 14336 
CSII_WORLD_METERS = 57344 
EARTH_CIRCUMFERENCE = 40075016.686

SOURCES = {
    "terrarium": "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png",
    "google_s": "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
    "google_m": "https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}",
    "osm": "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
}

# --- Core Utilities ---

def get_cached_tile(z, x, y, source):
    """Fetches tile from local cache or remote server."""
    cache_path = Path("cache") / source / str(z) / f"{x}_{y}.png"
    if cache_path.exists():
        return Image.open(cache_path).convert("RGB")

    headers = OSM_HEADERS if source == "osm" else None
    url = SOURCES[source].format(z=z, x=x, y=y)
    
    response = requests.get(url, headers=headers, timeout=15)
    if response.status_code != 200:
        raise RuntimeError(f"[FATAL] Tile fetch failed: {source} {z}/{x}/{y} (Status {response.status_code})")

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.open(io.BytesIO(response.content)).convert("RGB")
    img.save(cache_path)
    return img

def lat_lng_to_tile(lat, lng, zoom):
    """Converts coordinates to Slippy Map tile indices and pixel offsets."""
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    x_float = (lng + 180.0) / 360.0 * n
    y_float = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
    return int(x_float), int(y_float), int((x_float % 1) * 256), int((y_float % 1) * 256)

def get_master_bounds(lat, lng, anchor, side_meters):
    """Calculates the bounding box for a square area in decimal degrees."""
    R = 6378137 
    d_lat = (side_meters / R) * (180 / math.pi)
    d_lng = (side_meters / (R * math.cos(math.pi * lat / 180))) * (180 / math.pi)

    anchors = {
        "center": (lat + d_lat/2, lat - d_lat/2, lng - d_lng/2, lng + d_lng/2),
        "NW": (lat, lat - d_lat, lng, lng + d_lng),
        "NE": (lat, lat - d_lat, lng - d_lng, lng),
        "SW": (lat + d_lat, lat, lng, lng + d_lng),
        "SE": (lat + d_lat, lat, lng - d_lng, lng)
    }
    return anchors[anchor]    

# --- Processing Logic ---

def decode_terrarium(rgb_image):
    """Decodes RGB tiles into raw altitude (meters) with noise filtering."""
    data = np.array(rgb_image).astype(np.float32)
    # The Terrarium formula: (R * 256 + G + B / 256) - 32768
    heights = (data[:,:,0] * 256 + data[:,:,1] + data[:,:,2] / 256.0) - 32768
    
    # Clean outlier noise using median filter reference
    reference = median_filter(heights, size=5)
    outlier_mask = np.abs(heights - reference) > 200.0
    heights[outlier_mask] = reference[outlier_mask]
    return heights

def fetch_and_stitch(bounds, zoom, source, side_meters):
    """Downloads tiles and stitches them into a single cropped image."""
    lat_max, lat_min, lng_min, lng_max = bounds
    x_start, y_start, x_off, y_off = lat_lng_to_tile(lat_max, lng_min, zoom)
    x_end, y_end, _, _ = lat_lng_to_tile(lat_min, lng_max, zoom)

    width_tiles, height_tiles = (x_end - x_start + 1), (y_end - y_start + 1)
    m_per_px = (EARTH_CIRCUMFERENCE * math.cos(math.radians(lat_max))) / (2**(zoom + 8))
    target_px = int(side_meters / m_per_px)

    print(f"\nStitching {width_tiles}x{height_tiles} tiles for {source} at zoom {zoom}...")
    canvas = Image.new('RGB', (width_tiles * 256, height_tiles * 256))
    
    for i in range(width_tiles):
        for j in range(height_tiles):
            print(f"\rFetching tile {i*height_tiles + j + 1}/{width_tiles*height_tiles}: {source}/{zoom}/{x_start + i}_{y_start + j}...",
                end="",flush=True)
            tile = get_cached_tile(zoom, x_start + i, y_start + j, source)
            canvas.paste(tile, (i * 256, j * 256))
    
    print(f"\nCropping to {target_px}px square...")
    cropped = canvas.crop((x_off, y_off, x_off + target_px, y_off + target_px))
    
    # Save a debug copy of the raw stitch
    cropped.save(f"DEBUG_stitched_{source}_z{zoom}.png")
    return cropped

def calculate_optimal_zoom(lat, side_meters, target_res):
    """Calculates the minimum zoom level needed to meet or exceed a target resolution."""
    # C * cos(lat) / 2^(zoom + 8) = meters_per_pixel
    # target_res = side_meters / meters_per_pixel
    # Therefore: target_res = side_meters / (C * cos(lat) / 2^(zoom + 8))
    
    cos_lat = math.cos(math.radians(lat))
    # Solve for zoom:
    zoom = math.log2((target_res * EARTH_CIRCUMFERENCE * cos_lat) / (side_meters * 256))
    return math.ceil(zoom)


# --- Main Entry Point ---
def main():
    parser = argparse.ArgumentParser(description="Cities: Skylines II Map Grabber")
    parser.add_argument("name", help="Base name for output files")
    parser.add_argument("lat", type=float, help="Latitude")
    parser.add_argument("lng", type=float, help="Longitude")
    parser.add_argument("--layers", nargs="+", default=["elev", "sat", "map", "osm"], choices=["elev", "sat", "map", "osm"])
    parser.add_argument("--anchor", default="center", choices=["center", "NW", "NE", "SW", "SE"])
    parser.add_argument("--res", type=int, default=4096, choices=[1024, 2048, 4096, 8192, 16384])
    parser.add_argument("--zoom", type=int, default=0, help="Zoom level")
    args = parser.parse_args()

    opt_zoom = calculate_optimal_zoom(args.lat, CSII_CITY_METERS, args.res)
    if (args.zoom>0): zoom = args.zoom
    else: zoom = opt_zoom
    print(f"[INFO] Using zoom level {zoom} (Min required for {args.res}px: {opt_zoom})")

    # Define standard bounds
    city_bounds = get_master_bounds(args.lat, args.lng, args.anchor, CSII_CITY_METERS)
    l_max, l_min, ln_min, ln_max = city_bounds
    lat_center, lng_center = (l_max + l_min) / 2, (ln_max + ln_min) / 2
    world_bounds = get_master_bounds(lat_center, lng_center, "center", CSII_WORLD_METERS)    

    # 1. Elevation Layer Processing
    if "elev" in args.layers:
        print("--- Processing Elevation (World & City) ---")
        CITY_SIZE, MEGA_SIZE = args.res, args.res * 4
        
        # Stitch and Decode
        raw_img = fetch_and_stitch(world_bounds, zoom, "terrarium", CSII_WORLD_METERS)
        mega_heights = decode_terrarium(raw_img)
        
        # Resize to fixed mega resolution if necessary
        if mega_heights.shape != (MEGA_SIZE, MEGA_SIZE):
            interp = cv2.INTER_AREA if mega_heights.shape[0] > MEGA_SIZE else cv2.INTER_CUBIC
            mega_heights = cv2.resize(mega_heights, (MEGA_SIZE, MEGA_SIZE), interpolation=interp)

        # Handle Void values and scale
        valid_mask = mega_heights > 0
        h_min = mega_heights[valid_mask].min() if np.any(valid_mask) else 0
        mega_heights[~valid_mask] = h_min

        # Truncation logic for CSII height scale
        sealevel = 10.0
        h_min_adj = min(-sealevel, h_min - 10)
        h_max_adj = max(4096.0 - sealevel, mega_heights.max() + 10)
        
        print(f"Vertical Range: {h_min_adj:.2f}m to {h_max_adj:.2f}m ({h_max_adj - h_min_adj:.2f} total)")

        # Extract City Crop
        start = (MEGA_SIZE - CITY_SIZE) // 2
        city_data = mega_heights[start:start+CITY_SIZE, start:start+CITY_SIZE]
        world_data = cv2.resize(mega_heights, (CITY_SIZE, CITY_SIZE), interpolation=cv2.INTER_AREA)

        # Save 16-bit Maps
        def save_16bit(data, mi, ma, filename):
            norm = np.clip(((data - mi) / (ma - mi)) * 65535, 0, 65535).astype(np.uint16)
            Image.fromarray(norm).save(filename)

        save_16bit(city_data, h_min_adj, h_max_adj, f"{args.name}_heightmap.png")
        save_16bit(world_data, h_min_adj, h_max_adj, f"{args.name}_worldmap.png")
        print("Saved heightmaps (City & World).")

    # 2. Visual Layers Processing
    visuals = {"sat": ("google_s", "_satellite.png"), "map": ("google_m", "_map.png"), "osm": ("osm", "_osm.png")}
    for key, (source, suffix) in visuals.items():
        if key in args.layers:
            print(f"--- Processing {key.upper()} Layer ---")
            img = fetch_and_stitch(city_bounds, zoom, source, CSII_CITY_METERS)
            
            # Resizing logic
            resample = Image.Resampling.LANCZOS if img.size[0] > args.res else Image.Resampling.BICUBIC
            img.resize((args.res, args.res), resample=resample).save(f"{args.name}{suffix}")
            print(f"Saved: {args.name}{suffix}")

    print("\nGeneration finished.")

if __name__ == "__main__":
    main()