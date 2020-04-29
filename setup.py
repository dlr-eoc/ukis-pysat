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
    install_requires=open("requirements.txt").read().splitlines(),
    extras_require={"dev": ["sphinx >= 1.3", "sphinx_rtd_theme",],},
    classifiers=["Programming Language :: Python :: 3", "Operating System :: OS Independent",],
    python_requires=">=3.6",
)
