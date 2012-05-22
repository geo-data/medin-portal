# Created by Homme Zwaagstra
# 
# Copyright (c) 2010 GeoData Institute
# http://www.geodata.soton.ac.uk
# geodata@soton.ac.uk
# 
# Unless explicitly acquired and licensed from Licensor under another
# license, the contents of this file are subject to the Reciprocal
# Public License ("RPL") Version 1.5, or subsequent versions as
# allowed by the RPL, and You may not copy or use this file in either
# source code or executable form, except in compliance with the terms
# and conditions of the RPL.
# 
# All software distributed under the RPL is provided strictly on an
# "AS IS" basis, WITHOUT WARRANTY OF ANY KIND, EITHER EXPRESS OR
# IMPLIED, AND LICENSOR HEREBY DISCLAIMS ALL SUCH WARRANTIES,
# INCLUDING WITHOUT LIMITATION, ANY WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE, QUIET ENJOYMENT, OR
# NON-INFRINGEMENT. See the RPL for specific language governing rights
# and limitations under the RPL.
# 
# You can obtain a full copy of the RPL from
# http://opensource.org/licenses/rpl1.5.txt or geodata@soton.ac.uk
__version__ = 0.1

from sys import stdin
import argparse
import logging
from os.path import abspath, dirname, join, normpath, basename
import rdflib
import skos
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import string

def getVocabularies(fh):
    if fh.name == '<stdin>':
        path = dirname(__file__)
    else:
        path = dirname(abspath(fh.name))

    # the vocabularies we want to copy
    vocabularies = []
    for line in map(string.strip, fh.readlines()):
        if not line:
            continue
        if line.startswith('.'): # is it a relative filepath?
            line = normpath(join(path, line))
        logging.info('adding vocabulary to parse: %s', line)
        vocabularies.append(line)
    return vocabularies

def getGraph(vocabularies):
    from urllib2 import HTTPError

    # Parse the vocabularies into a RDF graph
    graph = rdflib.Graph()
    for uri in vocabularies:
        logging.info('parsing vocabulary %s', uri)
        try:
            graph.parse(uri)
        except (HTTPError, IOError), e:
            logging.warn('cannot load %s: %s', uri, str(e))

    return graph

def normalise_uri(uri):
    """
    Ensure a vocabulary URI is consistent
    """
    if uri.startswith('file://'):
        # strip off unnecessary dirname info so we have a consistent
        # reference
        return basename(uri)
    return uri.rstrip(u'/')

def main():
    """
    Update the local vocabulary database
    """

    parser = argparse.ArgumentParser(description='Update the Vocabulary SQLite database from the NERC Vocabulary Server.')
    parser.add_argument('--vocabularies', type=argparse.FileType('r'), default=stdin, metavar='FILE',
                        help='A file containing newline separated list of vocabulary resources to copy (defaults to STDIN)')
    parser.add_argument('file', metavar='FILE', nargs=1,
                        help='The SQLite database file to update')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    filename = abspath(args.file[0])

    # Annoyingly we have to register a plugin to deal with the
    # `text/xml` content type representing the RDF returned from the
    # NERC vocabulary server
    rdflib.plugin.register('text/xml', rdflib.plugin.Parser, 'rdflib.plugins.parsers.rdfxml', 'RDFXMLParser')

    try:
        engine = create_engine('sqlite:///%s' % filename) # get a handle on the local database

        # load the vocabularies
        vocabularies = getVocabularies(args.vocabularies)
        graph = getGraph(vocabularies)
        loader = skos.RDFLoader(graph, normalise_uri=normalise_uri)

        # get a session to the local database
        Session = sessionmaker(bind=engine)
        session = Session()

        # re-create the schema and load the vocabularies
        with session.begin(subtransactions=True):
            conn = session.connection()
            skos.Base.metadata.drop_all(conn)
            skos.Base.metadata.create_all(conn)

            session.add_all(loader.values())
        session.commit()

        del engine
        logging.info("Finished")
    except KeyboardInterrupt:
        logging.warn("Interrupted!")

if __name__ == '__main__':
    main()
