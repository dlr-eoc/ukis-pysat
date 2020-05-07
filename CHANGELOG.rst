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
- ``download.Source()``: Static method ``_prep_aoi()`` for on the fly perparation of aoi for queries #1
- ``download.Source()``: ``query()`` accepts now aoi in forms of geojson file with varying CRS or bounding box coordinates in Lat Lon #1
- requirements: pyproj #1

Fixed
*****
- fixed #7

Changed
*******
- ``download.Source()``: Moved all metadata mapping from ``query()`` to ``construct_metadata()`` #1
- ``download.Source()``: Changed ``_construct_metadata()`` to ``construct_metadata()`` and removed static #1
- ``download.Source()``: Simplified api queries in ``query()`` #1

[0.1.0] – 2020-04-29
--------------------
- first release
