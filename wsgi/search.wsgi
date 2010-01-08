# Third party modules
import selector                        # for URI based dispatch

# Custom modules
import medin

# Create a WSGI application
application = selector.Selector(consume_path=False)

# the default entry point for the search
application.add('[/]', GET=medin.search)

# display and navigate through the result set
application.add('/results', GET=medin.results)

# display the metadata
application.add('/metadata/{gid:digits}', GET=medin.metadata)

