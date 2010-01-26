# Third party modules
import selector                        # for URI based dispatch

# Custom modules
import medin, medin.error

class Selector(selector.Selector):
    status404 = medin.error.HTTPErrorRenderer('404 Not Found', 'The resource you specified could not be found')

# Create a WSGI application
application = Selector(consume_path=False)

# provide a choice of templates
application.add('[/]', GET=medin.TemplateChoice())

# the OpenSearch Description document
application.add('/opensearch/catalogue/{template}.xml', GET=medin.OpenSearch())

# the default entry point for the search
application.add('/{template}[/]', GET=medin.Search())

# create the app to return the required formats
result_formats = medin.ResultFormat(medin.HTMLResults, {'rss': medin.RSSResults})

# display and navigate through the result set
application.add('/{template}/catalogue[.{format:word}]', GET=result_formats)

# display the metadata
application.add('/{template}/catalogue/{gid:chunk}', GET=medin.Metadata())

# add our Error handler
application = medin.error.ErrorHandler(application)
