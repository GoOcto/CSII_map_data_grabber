# Cities: Skylines II Map Grabber (CSII_map_data_grabber)

A Python utility for generating game-ready heightmaps and visual overlays for Cities: Skylines II. It automates the process of fetching elevation data, stitching map tiles, and normalizing scales to fit the CSII engine requirements.

## Features
* Heightmap Generation: Creates both a 4,096px "City" heightmap (14.3km) and a "World" heightmap (57.3km) using 16-bit PNG encoding.
* Vertical Scaling: Automatically calculates and normalizes elevation to ensure consistent vertical scale across both maps.
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
| name |	Prefix for the output files. | Required |
| lat |	Latitude of the target location. | Required |
| lng |	Longitude of the target location. | Required |
| --layers |	Space-separated list: elev, sat, map, osm. | elev sat map osm |
| --anchor |	Anchor point for the coordinates: center, NW, NE, SW, SE. |	center |
| --res	| Resolution for visual layers: 4096, 8192, 16384. | 4096 |
| --zoom |Map zoom level (higher is more detail, but more tiles). | 15 |

## Technical Details
### Alignment
The script uses a reference size of 14,336 meters for the playable city area and 57,344 meters for the world area. These dimensions are specifically calculated to align with the Cities: Skylines II terrain grid.

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