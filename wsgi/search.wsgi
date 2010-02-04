# Third party modules
import selector                        # for URI based dispatch

# Custom modules
import medin, medin.error

class Selector(selector.Selector):
    status404 = medin.error.HTTPErrorRenderer('404 Not Found', 'The resource you specified could not be found')

# Create a WSGI application for URI delegation using Selector
# (http://lukearno.com/projects/selector/). The order that child
# applications are added is important; the most specific URL matches
# must be before the more generic ones.
application = Selector(consume_path=False)

# provide a choice of templates
application.add('[/]', GET=medin.TemplateChoice())

# the OpenSearch Description document
application.add('/opensearch/catalogue/{template}.xml', GET=medin.OpenSearch())

# the default entry point for the search
application.add('/{template}[/]', GET=medin.Search())

# create the app to return the required formats
result_formats = medin.ResultFormat(medin.HTMLResults, {'rss': medin.RSSResults,
                                                        'atom': medin.AtomResults})

# display and navigate through the result set
application.add('/{template}/catalogue[.{format:word}]', GET=result_formats)

# display the metadata
application.add('/{template}/catalogue/{gid:segment}', GET=medin.Metadata())

# get an image representing the metadata bounds.
application.add('/{template}/catalogue/{gid:segment}/extent.png', GET=medin.metadata_image)

# download the metadata
application.add('/{template}/catalogue/{gid:segment}/{format:segment}', GET=medin.metadata_download)

# add our Error handler
application = medin.error.ErrorHandler(application)
