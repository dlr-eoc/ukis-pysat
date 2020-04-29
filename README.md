[![UKIS](docs/ukis-logo.png)](https://www.dlr.de/eoc/en/desktopdefault.aspx/tabid-5413/10560_read-21914/) UKIS-pysat
==============

![Build Status](https://github.com/dlr-eoc/ukis-pysat/workflows/build/badge.svg)
[![PyPI version](https://img.shields.io/pypi/v/ukis-pysat)](https://pypi.python.org/pypi/ukis-pysat/)
[![Documentation Status](https://readthedocs.org/projects/ukis-pysat/badge/?version=latest)](https://ukis-pysat.readthedocs.io/en/latest/?badge=latest)
[![GitHub license](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://black.readthedocs.io/en/stable/)


The UKIS-pysat package provides generic classes and functions to query, access and process multi-spectral and SAR satellite images.

### download
Download satellites data from different sources (currently Earth Explorer, SciHub, local directory), deal with and structure metadata.


### data
Reading satellite data and performing simple, but cumbersome tasks.


### file
Work with you local satellite data files and read information out of file names and metadata files. Currently focusing on Sentinel-1.


Read the documentation for more details: [https://ukis-pysat.readthedocs.io](https://ukis-pysat.readthedocs.io/en/latest/).

## Example
Here's an example about some basic features, it might also help to read through the [tests](tests).
````python
from ukis_pysat.file import get_sentinel_scene_from_dir
from ukis_pysat.download import Source
from ukis_pysat.data import Image
from ukis_pysat.members import Datahub

download_source = Source(source=Datahub.Scihub)
download_source.download_image(product_srcid, product_uuid, target_dir)

with get_sentinel_scene_from_dir(target_dir) as (full_path, ident):
    img = Image(os.path_testfiles.join(full_path, 'pre_nrcs.tif'))
````


## Installation
The easiest way to install `pysat` is through pip. At least once we put this on pypi which might be never.
```shell
pip install ukis-pysat
```

in the meanwhile you could do something like this:
```bash
git clone https://github.com/dlr-eoc/ukis-pysat
cd ukis-pysat
conda env create -f environment.yml
conda activate ukis_pysat
```

### Dependencies
For the latest list of dependencies check the [requirements](setup.py:12).


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
This software is licensed under the [Apache 2.0 License](LICENSE).

Copyright (c) 2020 German Aerospace Center (DLR) * German Remote Sensing Data Center * Department: Geo-Risks and Civil Security

## Changelog
See [changelog](CHANGELOG.rst).

## Contributing
The UKIS team welcomes contributions from the community.
For more detailed information, see our guide on [contributing](CONTRIBUTING.md) if you're interested in getting involved.

## What is UKIS?
The DLR project Environmental and Crisis Information System (the German abbreviation is UKIS, standing for [Umwelt- und Kriseninformationssysteme](https://www.dlr.de/eoc/en/desktopdefault.aspx/tabid-5413/10560_read-21914/) aims at harmonizing the development of information systems at the German Remote Sensing Data Center (DFD) and setting up a framework of modularized and generalized software components.

UKIS is intended to ease and standardize the process of setting up specific information systems and thus bridging the gap from EO product generation and information fusion to the delivery of products and information to end users.

Furthermore the intention is to save and broaden know-how that was and is invested and earned in the development of information systems and components in several ongoing and future DFD projects.
