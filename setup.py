#!/usr/bin/env python3

from setuptools import setup, find_packages

setup(
    name="ukis-pysat",
    version="0.1.0",
    url="https://github.com/dlr-eoc/ukis-pysat",
    author="German Aerospace Center (DLR)",
    author_email="ukis-helpdesk@dlr.de",
    description="generic classes and functions to query, access and process multi-spectral and SAR satellite images",
    packages=find_packages(),
    install_requires=[
        "shapely==1.6.4",
        "numpy==1.18.1",
        "dask==2.14.0",
        "requests==2.23.0",
        "rasterio==1.1.0",
        "matplotlib==3.1.3",
        "sentinelsat==0.13",
        "landsatxplore==0.6",
        "pylandsat==0.2",
        "rio_toa==0.3.0",
        "utm==0.5.0",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
)
