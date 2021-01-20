from pystac import Item


class StacApiIo:
    def default_item_url_method(feature):
        return Item.from_dict(feature)

    ITEM_URL_IO = default_item_url_method
    """Like in PySTAC you can replace the default_item_url_method to expand the ability to read different file systems.
    For example, a client of the library might replace this class  member in it's own __init__.py with a method that 
    can read from another cloud storage.
    """

    @classmethod
    def build_url(cls, feature):
        """Read in Item"""
        return cls.ITEM_URL_IO(feature)
