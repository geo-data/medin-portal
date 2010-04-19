import sys, traceback, os
from TileCache.Service import Service, Layer, Cache, wsgiHandler  # for our TileCache service

class Areas(object):
    """
    Interface for interacting with areas stored in a sqlite database
    """

    def __init__(self, db):
        self._db = db

    def getArea(self, id):
        cur = self._db.cursor()
        cur.execute('SELECT name, minx, miny, maxx, maxy FROM areas WHERE id = ?', (id,))
        res = cur.fetchone()
        if res:
            return (res[0], tuple(res[1:]))
        return None

    def getAreaId(self, name, type):
        cur = self._db.cursor()
        name = '%'+name+'%'
        cur.execute('SELECT id FROM areas WHERE name like ? AND type = ? ORDER BY length(name)', (name, type))
        aid = cur.fetchone()
        if aid:
            return aid[0]
        return None

    def getAreaName(self, id):
        cur = self._db.cursor()
        cur.execute('SELECT name FROM areas WHERE id = ?', (id,))
        area = cur.fetchone()
        if area:
            return area[0]
        return None

    def getAreaType(self, id):
        cur = self._db.cursor()
        cur.execute('SELECT type FROM areas WHERE id = ?', (id,))
        area = cur.fetchone()
        if area:
            return area[0]
        return None

    def getBBOX(self, id):
        cur = self._db.cursor()
        cur.execute('SELECT minx, miny, maxx, maxy FROM areas WHERE id = ?', (id,))
        bbox = cur.fetchone()
        if bbox:
            return bbox
        return None

    def countries(self):
        cur = self._db.cursor()
        cur.execute('SELECT id, name FROM countries ORDER BY name')
        return [row for row in cur]

    def britishIsles(self):
        cur = self._db.cursor()
        cur.execute('SELECT id, name FROM british_isles')
        return [row for row in cur]

    def chartingProgressAreas(self):
        cur = self._db.cursor()
        cur.execute('SELECT id, name FROM charting_progress_areas')
        return [row for row in cur]

    def icesRectangles(self):
        cur = self._db.cursor()
        cur.execute('SELECT id, name FROM ices_rectangles')
        return [row for row in cur]

    def seaAreas(self):
        cur = self._db.cursor()
        cur.execute('SELECT id, name FROM sea_areas')
        return [row for row in cur]

    def __deepcopy__(self, memo):
        """
        Return a deepcopy of the current instance
        
        We don't want to make a deep copy of the database connection,
        as that is shared between copies. Not sharing it results in
        the database closing when an Areas instance is deleted, which
        affects all other copies in existence.
        """
        
        return self.__class__(self._db)

class TileService(Service):
    """Extends TileCache.Service to enhance configuration sources

    The new loadConfig method enables a ConfigParser instance to be
    passed in directly, rather than through filenames alone. This
    decouples the Service from its configuration source."""

    # Code adapted from TileCache.Service._load
    @classmethod
    def loadConfig (cls, config):
        cache = None
        metadata = {}
        layers = {}
        try:
            if config.has_section("metadata"):
                for key in config.options("metadata"):
                    metadata[key] = config.get("metadata", key)
            
            if config.has_section("tilecache_options"):
                if 'path' in config.options("tilecache_options"): 
                    for path in config.get("tilecache_options", "path").split(","):
                        sys.path.insert(0, path)
            
            cache = cls.loadFromSection(config, "cache", Cache)

            layers = {}
            for section in config.sections():
                if section in cls.__slots__: continue
                layers[section] = cls.loadFromSection(
                                        config, section, Layer, 
                                        cache = cache)
        except Exception, E:
            metadata['exception'] = E
            metadata['traceback'] = "".join(traceback.format_tb(sys.exc_traceback))
        return cls(cache, layers, metadata)

def get_tileservice(environ):
    global _tilecache_service

    try:
        return _tilecache_service
    except NameError:
        pass

    from medin.templates import TemplateLookup
    from cStringIO import StringIO
    from ConfigParser import ConfigParser

    # get the config information by merging the current environment
    # with the config template
    template_lookup = TemplateLookup(environ)
    lookup = template_lookup.lookup()
    mappath = os.path.join('config', 'tilecache.cfg')
    cache_dir = os.path.join(environ.root, 'tmp')
    template = lookup.get_template(mappath)
    cfg = template.render(cache_dir=cache_dir)

    # create the service from our configuration
    config = ConfigParser()
    cfg_fp = StringIO(cfg)
    config.readfp(cfg_fp)

    _tilecache_service = TileService.loadConfig(config)

    return _tilecache_service

# The TileCache WSGI handler
# Code adapted from TileCache.Services.wsgiApp
def tilecache (environ, start_response):

    svc = get_tileservice(environ)

    # Set the PATH_INFO and SCRIPT_NAME appropriately for wsgiHandler
    try:
        req = environ['selector.vars']['req']
        if req is None:
            raise KeyError('req not found in selector.vars')
    
        path_info = environ['PATH_INFO']
        environ['SCRIPT_NAME'] += path_info[:len(path_info)-len(req)]
        environ['PATH_INFO'] = req
    except KeyError:
        environ['SCRIPT_NAME'] += environ['PATH_INFO']
        environ['PATH_INFO'] = ''
        
    return wsgiHandler(environ, start_response, _tilecache_service)

def metadata_image(bbox, mapfile):
    """Create a metadata image"""

    from json import dumps as tojson
    import mapnik

    minx, miny, maxx, maxy = bbox

    # create the bounding box as a json string
    width, height = (maxx - minx, maxy - miny)
    min_dim = 0.0125                        # minimum dimension for display as a rectangle (in degrees)
    if width < min_dim or height < min_dim:   # it should be a point
        feature = { "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [minx, miny]
                        },
                    "properties": {
                        "type": "point"
                        }
                    }
        width, height = (9, 9)
    else:
        feature = { "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[minx, miny], [maxx, miny], [maxx, maxy], [minx, maxy], [minx, miny]]]
                        },
                    "properties": {
                        "type": "bbox"
                        }
                    }

    json = tojson(feature)

    # instantiate the map
    m = mapnik.Map(250, 250)
    mapnik.load_map_from_string(m, mapfile)

    # set the datasource for the last layer to show the bounding box
    datasource = mapnik.Ogr(file=json, layer='OGRGeoJSON')
    m.layers[-1].datasource = datasource

    # create an image of the area of interest with a border
    border = 80.0                       # percentage border
    dx = width * (border / 100)
    minx2 = minx - dx; maxx2 = maxx + dx
    dy = height * (border / 100)
    miny2 = miny - dy; maxy2 = maxy + dy

    # don't create a border larger than the globe's extent
    if minx2 < -180.0 or maxx2 > 180.0 or miny2 < -90.0 or maxy2 > 90.0:
        minx2 = minx; maxx2 = maxx; miny2 = miny; maxy2 = maxy
    
    bbox = mapnik.Envelope(mapnik.Coord(minx2, miny2), mapnik.Coord(maxx2, maxy2))
    m.zoom_to_box(bbox)
    image = mapnik.Image(m.width, m.height)
    mapnik.render(m, image)

    return image
