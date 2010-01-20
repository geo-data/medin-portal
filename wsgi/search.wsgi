# Third party modules
import selector                        # for URI based dispatch

# Custom modules
import medin

class Selector(selector.Selector):
    status404 = medin.HTTPErrorRenderer('404 Not Found', 'The resource you specified could not be found')

# Create a WSGI application
application = Selector(consume_path=False)

# provide a choice of templates
application.add('[/]', GET=medin.TemplateChoice())

# the OpenSearch Description document
application.add('/opensearch/catalogue/{template}.xml', GET=medin.OpenSearch())

# the default entry point for the search
application.add('/{template}[/]', GET=medin.Search())

# display and navigate through the result set
application.add('/{template}/catalogue[.{format:word}]', GET=medin.Results())

# display the metadata
application.add('/{template}/catalogue/{gid:digits}', GET=medin.Metadata())

# add our Error handler
application = medin.ErrorHandler(application)
