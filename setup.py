#!/usr/bin/env python3
import codecs
import os

from setuptools import setup, find_packages

with open(r"README.md", encoding="utf8") as f:
    long_description = f.read()


def read(rel_path):
    here = os.path.abspath(os.path.dirname(__file__))
    with codecs.open(os.path.join(here, rel_path), "r") as fp:
        return fp.read()


def get_version(rel_path):
    for line in read(rel_path).splitlines():
        if line.startswith("__version__"):
            delim = '"' if '"' in line else "'"
            return line.split(delim)[1]

        raise RuntimeError("Unable to find version string.")


# please also update requirements.txt for testing. Make sure package versions are the same in each subset.
extras_require = {
    "data": [
        "numpy",
        "pillow",
        "pystac>=1.0.0",
        "python-dateutil",
        "requests",
        "sentinelsat>=1.0.1",
        "shapely",
        "pydantic",
    ],
    "raster": [
        "numpy",
        "rasterio>=1.1.8",
        "rio_toa>=0.3.0",
        "shapely",
        "xmltodict"
    ],
}
extras_require["complete"] = list(set([v for req in extras_require.values() for v in req]))

extras_require["dev"] = sorted(
    extras_require["complete"]
    + [
        "dask[array]",
        "fiona",
        "landsatxplore>=0.13.0",
        "pandas",
        "pyproj>=3.0.0",
        "requests_mock",
        "utm>=0.7.0",
        "sphinx>=1.3",
        "sphinx_rtd_theme",
    ]
)

setup(
    name="ukis-pysat",
    version=get_version(os.path.join("ukis_pysat", "__init__.py")),
    url="https://github.com/dlr-eoc/ukis-pysat",
    author="German Aerospace Center (DLR)",
    author_email="ukis-helpdesk@dlr.de",
    license="Apache 2.0",
    description="generic classes and functions to query, access and process multi-spectral and SAR satellite images",
    zip_safe=False,
    packages=find_packages(),
    install_requires=[],
    extras_require=extras_require,
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: Apache Software License",
        "Topic :: Scientific/Engineering :: GIS",
    ],
    python_requires=">=3.7",
    long_description=long_description,
    long_description_content_type="text/markdown",
)
