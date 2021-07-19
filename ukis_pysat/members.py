from enum import Enum, auto

from pydantic import BaseModel


class Platform(Enum):
    Sentinel1 = "Sentinel-1"
    Sentinel2 = "Sentinel-2"
    Sentinel3 = "Sentinel-3"
    Landsat5 = "LANDSAT_TM_C1"
    Landsat7 = "LANDSAT_ETM_C1"
    Landsat8 = "LANDSAT_8_C1"


class Datahub(Enum):
    STAC_local = "STAC Catalog/Collection"
    EarthExplorer = "EarthExplorer"
    Scihub = "Scihub"
    STAC_API = "STAC API"

from typing import List
from pydantic import BaseModel


class Bands(BaseModel):
    LC08: list = [
        "B1.TIF",
        "B2.TIF",
        "B3.TIF",
        "B4.TIF",
        "B5.TIF",
        "B6.TIF",
        "B7.TIF",
        "B8.TIF",
        "B9.TIF",
        "B10.TIF",
        "B11.TIF",
        "BQA.TIF",
        "MTL.txt",
        "ANG.txt",
    ]
    LE07: list = [
        "B1.TIF",
        "B2.TIF",
        "B3.TIF",
        "B4.TIF",
        "B5.TIF",
        "B6_VCID_1.TIF",
        "B6_VCID_2.TIF",
        "B7.TIF",
        "B8.TIF",
        "BQA.TIF",
        "GCP.txt",
        "MTL.txt",
        "ANG.txt",
        "README.GTF",
    ]
    LT05: list = [
        "B1.TIF",
        "B2.TIF",
        "B3.TIF",
        "B4.TIF",
        "B5.TIF",
        "B6.TIF",
        "B7.TIF",
        "BQA.TIF",
        "GCP.txt",
        "MTL.txt",
        "VER.txt",
        "README.GTF",
        "ANG.txt",
    ]
    LM04: list = ["B1.TIF", "B2.TIF", "B3.TIF", "B4.TIF", "BQA.TIF", "GCP.txt", "MTL.txt", "VER.txt", "README.GTF"]
    LM03: list = ["B4.TIF", "B5.TIF", "B6.TIF", "B7.TIF", "BQA.TIF", "MTL.txt", "README.GTF"]
    LM02: list = ["B4.TIF", "B5.TIF", "B6.TIF", "B7.TIF", "BQA.TIF", "MTL.txt", "README.GTF"]
    LM01: list = ["B4.TIF", "B5.TIF", "B6.TIF", "B7.TIF", "BQA.TIF", "MTL.txt", "README.GTF"]


if __name__ == "__main__":
    m = Bands()
    a=m.json()
    print(a)