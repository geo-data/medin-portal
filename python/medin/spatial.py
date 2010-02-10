import sys, traceback, os
from TileCache.Service import Service, Layer, Cache, wsgiHandler  # for our TileCache service

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
    cache_dir = os.path.join(template_lookup.doc_root, 'tmp')
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
