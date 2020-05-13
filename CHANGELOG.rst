Changelog
=========

Added
~~~~~
something was added

Fixed
~~~~~
something was fixed

Changed
~~~~~~~
something was changed

[master]  (2020-XX-XX)
----------------------

Added
*****
- ``download.Source()``: Classes ``Metadata`` and ``MetadataCollection`` for metadata handling #13
- expanded metadata part in README #13 - requirements: pyfields
- ``download.Source()``: ``prep_aoi()`` for on the fly preparation of aoi for queries #1
- ``data.Image()``: method ``get_subset()`` to retrieve subset array and bounding box of image tile #12
- ``download.Source()``: ``query()`` accepts now aoi in forms of geojson file with varying CRS or bounding box coordinates in Lat Lon #1
- requirements: pyproj #1
- ``download.Source()``: added methods to filter and download metadata #4
- Sentinel3 test #10

Fixed
*****
- download.Source(): Improved geocoding quicklooks #5
- fixed #7

Changed
*******
- ``download.Source()``: Moved ``download_metadata()`` and ``filter_metadata()`` to ``Metadata`` class #13
- ``download.Source()``: Moved all metadata mapping from ``query()`` to ``construct_metadata()`` #1
- ``download.Source()``: Changed ``_construct_metadata()`` to ``construct_metadata()`` and removed static #1
- ``download.Source()``: Simplified api queries in ``query()`` #1
- ``download.Source()``: removed ``get_metadata()`` #4
- requirements: Removed matplotlib, pandas and dask optional #9

[0.1.0] – 2020-04-29
--------------------
- first release
