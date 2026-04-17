# Cities: Skylines II Map Grabber (CSII_map_data_grabber)

A Python utility for generating game-ready heightmaps and visual overlays for Cities: Skylines II. It automates the process of fetching elevation data, stitching map tiles, and normalizing scales to fit the CSII engine requirements.

## Features
* Heightmap Generation: Creates both a 4,096px "City" heightmap (14.3km) and a "World" heightmap (57.3km) using 16-bit PNG encoding.
* Vertical Normalization: The script calculates a global vertical range across the entire 57.3km world area. It applies a 10m offset for sea level and scales the 16-bit PNG so that h_min - 10m is 0 and h_max + 10m (or 4096m, whichever is higher) is 65535. This ensures the City and World maps share the exact same height scale for seamless importing.
* Visual Overlays: Downloads and stitches satellite imagery, road maps, or OpenStreetMap data to use as templates in the Map Editor.
* Intelligent Caching: Saves downloaded tiles locally to cache/ to speed up subsequent runs and reduce server load.
* Noise Filtering: Applies a median filter to elevation data to remove "terrarium" artifacts and outliers.

## Installation
### Prerequisites
* Python 3.8+
* Dependencies: opencv-python, numpy, pillow, requests, scipy

### Setup
```bash
pip install opencv-python numpy pillow requests scipy
```

### Usage
Run the script from the command line by providing a filename, latitude, and longitude.
```bash
python csii_grabber.py <name> <lat> <lng> [options]
```

#### Basic Example
To grab a satellite map for Banff, Alberta:
```bash
python csii_grabber.py banff 51.188263 -115.546593 --layers sat --zoom 15
```

#### Arguments

| Argument | Description | Default |
| -------- | ----------- | ------- |
| name | Prefix for the output files. | Required |
| lat | Latitude of the target location. | Required |
| lng | Longitude of the target location. | Required |
| --layers | Space-separated list: elev, sat, map, osm. | elev sat map osm |
| --anchor | Anchor point for the coordinates: center, NW, NE, SW, SE. | center |
| --res | Resolution for visual layers: 1024, 2048, 4096, 8192, 16384. | 4096 |
| --zoom | Map zoom level (higher is more detail, but more tiles). | automatically calculated from res |

Only use zoom to specifically override the automatic calculation which is based on the requested resolution.

The anchor is used when your coordinates specify one corner of your CSII map rather than the center. So, if your coordinates are for the top left corner of your map you would specify `--anchor NW`.

## Technical Details

### Alignment

The script uses a reference size of 14,336 meters for the playable city area and 57,344 meters for the world area. These dimensions are specifically used in the  City Skylines II game.

CSII map editor usually applies a scaler to your heightmaps of 4096. The code tries to honor this default when it generates the heightmap and worldmap. If your particular map covers more than 4096 vertical units, then the script will tell you what scale value to use. It will add a small margin so that your heightmap does not contain the most extreme high and low values which could make adding sealevel and other map features difficult.

> 💡 **Tip:** When the output says: "Vertical Range: -10.00m to 4531.28m (4541.28 total)" you will want to use 4541 as your scaler to properly represent the range of elevations in the data. You will only need to worry about this in areas of great relief.

* The code may output one or more DEBUG_stitched_... PNG files. These are so you can verify the integrity of the data. These files are the results of stitching together multiple tiles from a source. The final files are derived directly from these ones by cropping and scaling to the precise coordinates.




### Elevation & Vertical Scaling

The script automatically processes raw "Terrarium" RGB tiles into a 16-bit grayscale format compatible with Cities: Skylines II. To ensure the best results in the Map Editor, it follows a specific normalization logic:

#### How it works

* Global Range Calculation: The script analyzes the entire 57.3km world area to find the absolute minimum and maximum elevations.
* Buffers: It applies a 10.0m sea-level offset and an additional 10m vertical padding to the boundaries.
* Normalization: The vertical data is mapped to the 16-bit range ($0$ to $65535$) where the lowest point ($h_{min} - 10$) becomes black and the highest point ($h_{max} + 10$) becomes white.

> 💡 **Tip:** Cities: Skylines II defaults to a height scale of 4096. If your map covers significant mountain ranges or deep trenches, check the script's console output:

```bash
Vertical Range: -10.00m to 4531.28m (4541.28 total)
```

In this case, you should set your Offset to -10 and your Scale to 4541 in the Map Editor to ensure your terrain isn't flattened or clipped.






### Output Files

* [name]_heightmap.png: 16-bit grayscale PNG for the 14.3km playable area.
* [name]_worldmap.png: 16-bit grayscale PNG for the 57.3km background/world area.
* [name]_satellite.png: High-resolution satellite imagery (Google).
* [name]_map.png: Standard road map view (Google).
* [name]_osm.png: OpenStreetMap data.

OpenStreetMap can be very useful for railways, electric lines, seaways, etc.

### Data Sources
* Elevation: Amazon/Mapzen Terrarium tiles.
* Satellite/Map: Google Maps.
* OSM: OpenStreetMap.

### Troubleshooting
* Memory Usage: Stitching at zoom levels above 16 or at 16k resolutions requires significant RAM.
* Elevation Voids: The script automatically masks and fills "void" or "no-data" pixels in the elevation data with the minimum detected height to prevent bottomless pits in-game.