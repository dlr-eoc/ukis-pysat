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

[0.1.1] - 2020-05-06
------------------
* Issue #1
* Added
- download.Source(): Static method _prep_aoi() for on the fly perparation of aoi for queries
- download.Source(): query() accepts now aoi in forms of geojson file with varying CRS or bounding box coordinates in Lat Lon
* Changed
- download.Source(): Moved all metadata mapping from query() to construct_metadata()
- download.Source(): Changed _construct_metadata() to construct_metadata() and removed static
- download.Source(): Simplified api queries in query()

[0.1.0] – 2020-04-29
------------------
* first release
