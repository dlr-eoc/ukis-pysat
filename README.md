[![UKIS](https://raw.githubusercontent.com/dlr-eoc/ukis-pysat/master/docs/ukis-logo.png)](https://www.dlr.de/eoc/en/desktopdefault.aspx/tabid-5413/10560_read-21914/) UKIS-pysat
==============

![Build Status](https://github.com/dlr-eoc/ukis-pysat/workflows/build/badge.svg)
[![codecov](https://codecov.io/gh/dlr-eoc/ukis-pysat/branch/master/graph/badge.svg)](https://codecov.io/gh/dlr-eoc/ukis-pysat)
[![PyPI version](https://img.shields.io/pypi/v/ukis-pysat)](https://pypi.python.org/pypi/ukis-pysat/)
[![Documentation Status](https://readthedocs.org/projects/ukis-pysat/badge/?version=latest)](https://ukis-pysat.readthedocs.io/en/latest/?badge=latest)
[![GitHub license](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://black.readthedocs.io/en/stable/)


The UKIS-pysat package provides generic classes and functions to query, access and process multi-spectral and SAR satellite images.

### data
Download satellites data from different sources (currently Earth Explorer, SciHub, local directory), deal with and structure metadata.


### file
Work with you local satellite data files and read information out of file names and metadata files. Currently focusing on Sentinel-1.


### raster
Reading satellite data and performing simple, but cumbersome tasks.


Read the documentation for more details: [https://ukis-pysat.readthedocs.io](https://ukis-pysat.readthedocs.io/en/latest/).

## Example
Here's an example about some basic features, it might also help to read through the [tests](https://github.com/dlr-eoc/ukis-pysat/blob/master/tests).

````python
from ukis_pysat.data import Source
from ukis_pysat.file import get_sentinel_scene_from_dir
from ukis_pysat.members import Datahub, Platform
from ukis_pysat.raster import Image


# connect to Scihub and query metadata (returns MetadataCollection)
src = Source(Datahub.Scihub)
meta = src.query_metadata(
    platform=Platform.Sentinel2,
    date=("20200101", "NOW"),
    aoi=(11.90, 51.46, 11.94, 51.50),
    cloud_cover=(0, 50),
)

# inspect MetadataCollection with Pandas
meta_df = meta.to_pandas()
print(meta_df[["srcid", "producttype", "cloudcoverpercentage", "size", "srcuuid"]])

# filter MetadataCollection by producttype
meta.filter(filter_dict={"producttype": "S2MSI1C"})

# save Metadata items as GeoJSON
meta.save(target_dir="target_dir/")

# get product_uuid of first metadata item
uuid = meta.items[0].to_dict()["srcuuid"]

# download geocoded quicklook and image
src.download_quicklook(platform=Platform.Sentinel2, product_uuid=uuid, target_dir="target_dir/")
src.download_image(platform=Platform.Sentinel2, product_uuid=uuid, target_dir="target_dir/")

# get sentinel scene from directory
with get_sentinel_scene_from_dir(target_dir) as (full_path, ident):
    img = Image(os.path_testfiles.join(full_path, 'pre_nrcs.tif'))
````

### Environment variables to configure Datahub credentials
To use ``ukis_pysat.data`` and to download from the respective Datahub you need to set the credentials as environment variables.

For EarthExplorer that's: \
``EARTHEXPLORER_USER=your_username`` \
``EARTHEXPLORER_PW=your_password``

For SciHub that's: \
``SCIHUB_USER=your_username`` \
``SCIHUB_PW=your_password``

## Installation
The easiest way to install `pysat` is through pip. Be aware, that Rasterio requires GDAL >= 1.11, < 3.1.

Most users will want to do this:
```shell
pip install ukis-pysat[complete]  # install everything
```

There's also some lighter versions with less dependencies:

```shell
pip install ukis-pysat  # only install core dependencies (ukis_pysat.file can be used)

pip install ukis-pysat[data]  # also install dependencies for ukis_pysat.data

pip install ukis-pysat[raster]  # also install dependencies for ukis_pysat.raster
```

Some helper functions might need additional dependencies like `pandas`, `dask[array]` or `utm`. If this is the case you will receive an `ImportError`.

You can also do this, even though `environment.yml` is updated less often:
```bash
git clone https://github.com/dlr-eoc/ukis-pysat
cd ukis-pysat
conda env create -f environment.yml
conda activate ukis_pysat
```

### Dependencies
For the latest list of dependencies check the [requirements](https://github.com/dlr-eoc/ukis-pysat/blob/master/requirements.txt).


## Contributors
The UKIS team creates and adapts libraries which simplify the usage of satellite data. Our team includes (in alphabetical order):
* Boehnke, Christian
* Fichtner, Florian
* Mandery, Nico
* Martinis, Sandro
* Riedlinger, Torsten
* Wieland, Marc

German Aerospace Center (DLR)

## Licenses
This software is licensed under the [Apache 2.0 License](https://github.com/dlr-eoc/ukis-pysat/blob/master/LICENSE).

Copyright (c) 2020 German Aerospace Center (DLR) * German Remote Sensing Data Center * Department: Geo-Risks and Civil Security

## Changelog
See [changelog](https://github.com/dlr-eoc/ukis-pysat/blob/master/CHANGELOG.rst).

## Contributing
The UKIS team welcomes contributions from the community.
For more detailed information, see our guide on [contributing](https://github.com/dlr-eoc/ukis-pysat/blob/master/CONTRIBUTING.md) if you're interested in getting involved.

## What is UKIS?
The DLR project Environmental and Crisis Information System (the German abbreviation is UKIS, standing for [Umwelt- und Kriseninformationssysteme](https://www.dlr.de/eoc/en/desktopdefault.aspx/tabid-5413/10560_read-21914/) aims at harmonizing the development of information systems at the German Remote Sensing Data Center (DFD) and setting up a framework of modularized and generalized software components.

UKIS is intended to ease and standardize the process of setting up specific information systems and thus bridging the gap from EO product generation and information fusion to the delivery of products and information to end users.

Furthermore the intention is to save and broaden know-how that was and is invested and earned in the development of information systems and components in several ongoing and future DFD projects.
