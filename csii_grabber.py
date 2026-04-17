import argparse
import io
import math
from pathlib import Path

import cv2
import numpy as np
import requests
from PIL import Image
from scipy.ndimage import median_filter

# Disable the DecompressionBombWarning for large map stitches
Image.MAX_IMAGE_PIXELS = None

# Constants
OSM_HEADERS = {
    'User-Agent': 'CS2-MapGenerator/1.0 (https://github.com/GoOcto/CSII-maps; paul@goocto.com)'
}

# Playable map size in meters (21 tiles * 75 blocks/tile * 8m/block)
# but the CSII game engine expects 14336 for alignment reasons 
CSII_CITY_METERS = 14336 
CSII_WORLD_METERS = 57344 # required for the "world" heightmap 
EARTH_CIRCUMFERENCE = 40075016.686

def get_cached_tile(z, x, y, source):
    cache_path = Path("cache") / source / str(z) / f"{x}_{y}.png"
    if cache_path.exists():
        return Image.open(cache_path).convert("RGB")

    urls = {
        "terrarium": ( f"https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png", None ),
        "google_s": ( f"https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", None ),
        "google_m": ( f"https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}", None ),
        "osm": ( f"https://tile.openstreetmap.org/{z}/{x}/{y}.png", OSM_HEADERS )
    }

    target_url, target_headers = urls[source]
    response = requests.get(target_url, headers=target_headers, timeout=15)

    if response.status_code != 200:
        raise RuntimeError(f"[FATAL] Tile fetch failed: {source} {z}/{x}/{y} (Status {response.status_code})")

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.open(io.BytesIO(response.content)).convert("RGB")
    img.save(cache_path)
    return img

def lat_lng_to_tile(lat, lng, zoom):
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    x_float = (lng + 180.0) / 360.0 * n
    y_float = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
    return int(x_float), int(y_float), int((x_float % 1) * 256), int((y_float % 1) * 256)

def get_master_bounds(lat, lng, anchor, side_meters):
    """Calculates the fixed reference bounding box."""
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


def decode_terrarium(rgb_image):
    """Decodes RGB tiles into raw altitude (meters)."""
    data = np.array(rgb_image).astype(np.float32)
    heights = (data[:,:,0] * 256 + data[:,:,1] + data[:,:,2] / 256.0) - 32768
    # Clean noise
    reference = median_filter(heights, size=5)
    outlier_mask = np.abs(heights - reference) > 200.0
    heights[outlier_mask] = reference[outlier_mask]
    return heights

def get_stitched_raw(bounds, zoom, source, side_meters):
    """Returns a raw numpy array of altitudes or RGB data for a specific area."""
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
    
    print(f"Saving stitched image for debugging...", flush=True)
    canvas.save(f"DEBUG_stitched_{source}_z{zoom}.png")

    print(f"Cropping {target_px}px square starting at ({x_off}, {y_off})...", flush=True)
    box = (x_off, y_off, x_off + target_px, y_off + target_px)
    cropped = canvas.crop(box).copy()
    del canvas  # explicitly delete the large canvas to free memory

    print(f"Cropped size: {cropped.size}, target_px: {target_px}", flush=True)
    return cropped, target_px   
    #return np.array(cropped), target_px


def main():
    parser = argparse.ArgumentParser(description="Cities: Skylines II Map Grabber")
    parser.add_argument("name", help="Base name for output files")
    parser.add_argument("lat", type=float, help="Latitude")
    parser.add_argument("lng", type=float, help="Longitude")
    parser.add_argument("--layers", nargs="+", default=["elev", "sat", "map", "osm"], 
                        choices=["elev", "sat", "map", "osm"], help="Specific layers to generate")
    parser.add_argument("--anchor", default="center", choices=["center", "NW", "NE", "SW", "SE"])
    parser.add_argument("--res", type=int, default=4096, choices=[4096, 8192, 16384])
    parser.add_argument("--zoom", type=int, default=15, help="Zoom level")
    
    args = parser.parse_args()


    # 1. Establish Master City Bounds
    city_bounds = get_master_bounds(args.lat, args.lng, args.anchor, CSII_CITY_METERS)
    l_max, l_min, ln_min, ln_max = city_bounds
    
    # 2. Derive World Bounds from City Center
    lat_center = (l_max + l_min) / 2
    lng_center = (ln_max + ln_min) / 2
    world_bounds = get_master_bounds(lat_center, lng_center, "center", CSII_WORLD_METERS)    
    city_bounds = get_master_bounds(lat_center, lng_center, "center", CSII_CITY_METERS)


    if "elev" in args.layers:
        print("--- Collection Phase: Elevation Mega-Stitch (57.3km) ---")
        
        # 1. Define fixed Mega-Resolution
        MEGA_SIZE = 16384
        CITY_SIZE = 4096
        
        # Request data at mega resolution
        raw_rgb, _ = get_stitched_raw(world_bounds, args.zoom, "terrarium", CSII_WORLD_METERS)
        raw_heights_orig = decode_terrarium(raw_rgb)
        
        # 2. Force to 16k x 16k if the raw stitch differs
        if raw_heights_orig.shape != (MEGA_SIZE, MEGA_SIZE):
            print(f"Resizing raw data to {MEGA_SIZE}x{MEGA_SIZE}...")
            interp = cv2.INTER_AREA if raw_heights_orig.shape[0] > MEGA_SIZE else cv2.INTER_CUBIC
            mega_heights = cv2.resize(raw_heights_orig, (MEGA_SIZE, MEGA_SIZE), interpolation=interp)
        else:
            mega_heights = raw_heights_orig



        # Create a mask for valid data (Terrarium void is usually exactly -32768)
        # We use > -10000 as a safe buffer for any real-world elevation
        valid_mask = mega_heights > 0

        if not np.any(valid_mask):
            print("Warning: No valid elevation data found!")
            h_min, h_max = 0, 1 # Fallback
        else:
            h_min = mega_heights[valid_mask].min()
            h_max = mega_heights[valid_mask].max()

        # Replace the 'void' values with the minimum real elevation 
        # so they don't appear as black pits in your heightmap
        mega_heights[~valid_mask] = h_min

        print(f"\nVERTICAL SCALE REPORT:")
        print(f"Min: {h_min:.2f}m | Max: {h_max:.2f}m | Range: {h_max - h_min:.2f}m\n")

        # try to use the CSII default height scale = 4096.0
        sealevel = 10.0
        h_min, h_max = min(-sealevel, h_min-10), max(4096.0-sealevel, h_max+10)

        print(f"\nTruncated:")
        print(f"Min: {h_min:.2f}m | Max: {h_max:.2f}m | Range: {h_max - h_min:.2f}m\n")


        # 3. Extract Central 4k Crop (City)
        start = (MEGA_SIZE - CITY_SIZE) // 2
        city_final = mega_heights[start:start+CITY_SIZE, start:start+CITY_SIZE]

        # 4. Downsample Mega to 4k (World)
        world_final = cv2.resize(mega_heights, (CITY_SIZE, CITY_SIZE), interpolation=cv2.INTER_AREA)

        # 5. Normalize and Save
        # Reuse normalization parameters to ensure vertical consistency between files
        def scale_16bit(data, mi, ma):
            return np.clip(((data - mi) / (ma - mi)) * 65535, 0, 65535).astype(np.uint16)

        Image.fromarray(scale_16bit(world_final, h_min, h_max)).save(f"{args.name}_worldmap.png")
        Image.fromarray(scale_16bit(city_final, h_min, h_max)).save(f"{args.name}_heightmap.png")
        print(f"Saved 16-bit heightmaps: {args.name}_heightmap.png (City) and {args.name}_worldmap.png (World)")


    # 2. Handle Visual Layers
    visuals = {"sat": ("google_s", "_satellite.png"), "map": ("google_m", "_map.png"), "osm": ("osm", "_osm.png")}
    for key in (set(args.layers) & visuals.keys()):
        source, suffix = visuals[key]
        img, _ = get_stitched_raw(city_bounds, args.zoom, source, CSII_CITY_METERS)

        resample_filter = Image.Resampling.LANCZOS if img.size[0] > args.res else Image.Resampling.BICUBIC
        final = img.resize((args.res, args.res), resample=resample_filter)
        final.save(f"{args.name}{suffix}")        

        print(f"Saved file: {args.name}{suffix}")

    print("\nGeneration finished.")

if __name__ == "__main__":
    main()

# example:
# python csii_grabber.py banff 51.188263 -115.546593 --anchor center --res 4096 --layers sat --zoom 15

