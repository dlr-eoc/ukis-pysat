from enum import Enum, auto


class Platform(Enum):
    Sentinel1 = "Sentinel-1"
    Sentinel2 = "Sentinel-2"
    Sentinel3 = "Sentinel-3"
    Landsat5 = "LANDSAT_TM_C1"
    Landsat7 = "LANDSAT_ETM_C1"
    Landsat8 = "LANDSAT_8_C1"


class Datahub(Enum):
    Directory = "Directory"
    EarthExplorer = "EarthExplorer"
    Scihub = "Scihub"
    StacApi = "stac API"
