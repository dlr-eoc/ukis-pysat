from pystac import Item

import warnings

class STACAPI_IO:
    def default_item_method(feature):
        warnings.warn("This script is going to be deleted. Please use the pystac-client.", DeprecationWarning)
        return Item.from_dict(feature)

    read_item_method = default_item_method
    """Like in PySTAC you can replace the default_item_method to expand the ability to read different file systems.
    For example, a client of the library might replace this class  member in it's own __init__.py with a method that 
    can read from another cloud storage.
    """

    @classmethod
    def build_url(cls, feature):
        """Read in Item"""
        return cls.read_item_method(feature)
