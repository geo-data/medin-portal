# Created by Homme Zwaagstra
# 
# Copyright (c) 2012 GeoData Institute
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

"""
An interface to the portal vocabularies
"""

import skos
from sqlalchemy import create_engine, or_
from sqlalchemy.orm import sessionmaker
from collections import Mapping

class Vocabularies(Mapping):
    def __init__(self, engine):
        # get a session to the local database
        Session = sessionmaker(bind=engine)
        self.session = Session()

    def __getitem__(self, key):
        obj = self.session.query(skos.Object).filter(skos.Object.uri == key).first()
        if obj is None:
            raise KeyError(key)
        return obj

    def __len__(self):
        return self.session.query(skos.Object).count()

    def __iter__(self):
        return iter(self.session.query(skos.Object.uri))

    def getMatchingConcept(self, term, collection):
        """
        Retrieve a matching term from a particular collection

        The match is case insensitive.
        """

        return self.session.query(skos.Concept)\
            .join(skos.Concept.collections)\
            .filter(skos.Collection.uri == collection)\
            .filter(skos.Concept.prefLabel.ilike(term)).first()

    def getConceptsHavingBroader(self, source_collection, broader_member):
        """
        Retrieve all concepts from a collection having a particular broader member
        """

        sql = """SELECT o.*
FROM object o,
     concept c1,
     concepts2collections c2c1,
     concept_broader cb1
WHERE o.uri = c1.uri
AND c1.uri = c2c1.concept_uri
AND c2c1.collection_uri = ?
AND c1.uri = cb1.narrower_uri
AND cb1.broader_uri = ?
ORDER BY c1.prefLabel"""
        conn = self.session.connection()
        result = conn.execute(sql, [source_collection, broader_member])
        for concept in self.session.query(skos.Concept).instances(result):
            yield concept

    def getSubThemeIdsForDataThemeId(self, data_theme_id):
        broader = 'http://vocab.nerc.ac.uk/collection/P23/current/' + data_theme_id
        return self.getIdsFromConcepts(self.getConceptsHavingBroader('http://vocab.nerc.ac.uk/collection/P03/current', broader))

    def getParameterIdsForSubThemeId(self, sub_theme_id):
        broader = 'http://vocab.nerc.ac.uk/collection/P03/current/' + sub_theme_id
        return self.getIdsFromConcepts(self.getConceptsHavingBroader('http://vocab.nerc.ac.uk/collection/P02/current', broader))
            
    def getDataThemeIds(self):
        return self.getMemberIdsFromCollection('http://vocab.nerc.ac.uk/collection/P23/current')

    def getDataFormatIds(self):
        return self.getIdsFromConcepts(self['http://vocab.nerc.ac.uk/collection/M01/current'].members.values())
    
    def getDataFormatsFromIds(self, ids):
        return self.getConceptsFromIds(ids, 'http://vocab.nerc.ac.uk/collection/M01/current')

    def getAccessTypeIds(self):
        return self.getIdsFromConcepts(self['medin-access-types.xml'].members.values())

    def getAccessTypesFromIds(self, ids):
        return self.getConceptsFromIds(ids, 'medin-access-types.xml', '%s')
    
    def getMemberIdsFromCollection(self, uri):
        concepts = self[uri].members.values()
        concepts.sort(cmp=lambda a, b: cmp(a.prefLabel, b.prefLabel))
        return self.getIdsFromConcepts(concepts)

    def getConceptsFromIds(self, ids, collection_uri, ilike='%%/%s'):
        filt = or_()
        for id_ in ids:
            filt.append(skos.Concept.uri.ilike(ilike % id_))

        return self.session.query(skos.Concept)\
            .join(skos.Concept.collections)\
            .filter(skos.Collection.uri == collection_uri)\
            .filter(filt).all()
        
    def getDataThemesFromIds(self, ids):
        return self.getConceptsFromIds(ids, 'http://vocab.nerc.ac.uk/collection/P23/current')

    def getSubThemesFromIds(self, ids):
        return self.getConceptsFromIds(ids, 'http://vocab.nerc.ac.uk/collection/P03/current')

    def getParametersFromIds(self, ids):
        return self.getConceptsFromIds(ids, 'http://vocab.nerc.ac.uk/collection/P02/current')
    
    def getIdsFromConcepts(self, concepts):
        return [(c.uri.rsplit('/', 1)[-1], c.prefLabel) for c in concepts]

    def getParametersFromDataThemeIds(self, ids):
        if not ids:
            return []

        sql = """SELECT c1.prefLabel
FROM concept c1,
     concepts2collections c2c1,
     concept c2,
     concepts2collections c2c2,
     concept_broader cb1,
     concept c3,
     concepts2collections c2c3,
     concept_broader cb2
WHERE c1.uri = c2c1.concept_uri
AND c2c1.collection_uri = 'http://vocab.nerc.ac.uk/collection/P02/current'

AND c2.uri = c2c2.concept_uri
AND c2c2.collection_uri = 'http://vocab.nerc.ac.uk/collection/P03/current'

AND c1.uri = cb1.narrower_uri
AND c2.uri = cb1.broader_uri

AND c3.uri = c2c3.concept_uri
AND c2c3.collection_uri = 'http://vocab.nerc.ac.uk/collection/P23/current'

AND c2.uri = cb2.narrower_uri
AND c3.uri = cb2.broader_uri

AND c3.uri IN (%s)""" % ','.join('?' * len(ids))

        conn = self.session.connection()
        params = ['http://vocab.nerc.ac.uk/collection/P23/current/%s' % id_ for id_ in ids]
        return [row[0] for row in conn.execute(sql, params)]

    def getParametersFromSubThemeIds(self, ids):
        if not ids:
            return []

        sql = """SELECT c1.prefLabel
FROM concept c1,
     concepts2collections c2c1,
     concept c2,
     concepts2collections c2c2,
     concept_broader cb1
WHERE c1.uri = c2c1.concept_uri
AND c2c1.collection_uri = 'http://vocab.nerc.ac.uk/collection/P02/current'

AND c2.uri = c2c2.concept_uri
AND c2c2.collection_uri = 'http://vocab.nerc.ac.uk/collection/P03/current'

AND c1.uri = cb1.narrower_uri
AND c2.uri = cb1.broader_uri

AND c2.uri IN (%s)""" % ','.join('?' * len(ids))
        conn = self.session.connection()
        params = ['http://vocab.nerc.ac.uk/collection/P03/current/%s' % id_ for id_ in ids]
        return [row[0] for row in conn.execute(sql, params)]
