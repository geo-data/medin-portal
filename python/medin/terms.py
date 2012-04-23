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

"""
Module for connecting to and querying the SeaDataNet Common Vocabularies Web Service

The module uses the WS SOAP interface. Further details are available at:

- http://www.seadatanet.org/standards_software/common_vocabularies
- http://www.bodc.ac.uk/products/web_services/vocab/
"""

import os
import suds

class VocabError(Exception):

    @property
    def message(self):
        return self.args[0]

class Vocabulary(object):
    
    def __init__(self, wsdl=None):
        if wsdl is None:
            # from http://www.bodc.ac.uk/extlink/http%3A//vocab.ndg.nerc.ac.uk/1.1/VocabServerAPI_dl.wsdl
            wsdl = 'file://%s' % os.path.abspath(os.path.join(os.path.dirname(__file__), 'data', 'VocabServerAPI_dl.wsdl'))

        self.client = suds.client.Client(wsdl)

    def getListKey(self, list_id):
        return 'http://vocab.ndg.nerc.ac.uk/list/%s/current' % list_id

    def _callService(self, method, *args, **kwargs):
        """
        Wrap the call to the SOAP service with some error checking
        """
        from suds import WebFault
        from urllib2 import URLError, HTTPError
        
        try:
            return method(*args, **kwargs)
        except WebFault, e:
            raise VocabError(e.args[0])
        except HTTPError, e:
            raise VocabError(str(e))
        except URLError, e:
            try:
                status, msg = e.reason
            except ValueError:
                msg = str(e.reason)

            raise VocabError(msg)

    def lookupTerm(self, list_id, term):
        """
        Return the definition of a term based on the entry key term

        If the term does not match the 'short' entry key, then the
        'long' entry key is tried instead.
        """
        listKey = self.getListKey(list_id)
        r = self._callService(self.client.service.verifyTerm, listKey, term, 'short')
        try:
            term = r.verifiedTerm
        except AttributeError:
            # try looking up the term as a 'long' entry
            r = self._callService(self.client.service.verifyTerm, listKey, term, 'long')
            try:
                term = r.verifiedTerm
            except AttributeError:
                raise LookupError('The term \'%s\' does not exist in the list %s' % (term, listKey))

        return dict(long=term.entryTerm,
                    short=term.entryTermAbbr,
                    defn=term.entryTermDef,
                    key=term.entryKey)

    def getList(self, list_id):
        """
        Return all entries in a list
        """
        listKey = self.getListKey(list_id)
        r = self._callService(self.client.service.getList, listKey)

        try:
            return [dict(term=entry.entryTerm,
                         abbr=entry.entryTermAbbr,
                         defn=entry.entryTermDef) for entry in r[0]]
        except TypeError:
            return []

    def getRelated(self, list_id, term):
        """Get related terms"""
        related = {}
        def getRelationship(relationship, record):
            try:
                related[relationship] = [term.entryTerm for term in record['%sMatch' % relationship]]
            except AttributeError:
                pass

        try:
            term = self.lookupTerm(list_id, term)
        except LookupError:
            return related

        recordKey = [term['key']]
        objectKey = []
        predicate = 255
        inference = 'true'
        r = self._callService(self.client.service.getRelatedRecordByTerm, recordKey, predicate, objectKey, inference)

        record = r.codeTableRecord[0]
        getRelationship('minor', record)
        getRelationship('exact', record)
        getRelationship('broad', record)
        getRelationship('narrow', record)

        return related

class CachedVocabulary(Vocabulary):
    """
    Vocabulary that caches lists returned by getList()

    You can specify the lifetime of a list before it is refreshed by
    passing a value in seconds to the constructor. The cache is shared
    across Vocabulary instances.
    """

    _cache = {}
    
    def __init__(self, lifetime, *args, **kwargs):
        super(CachedVocabulary, self).__init__(*args, **kwargs)
        self.lifetime = lifetime

    def refreshCachedList(self, list_id):
        from time import time
        # get the list from the inherited class
        list_ = super(CachedVocabulary, self).getList(list_id)
        self._cache[list_id] = (time(), list_)
        return list_

    def getList(self, list_id):
        from time import time

        cache_time = 0
        try:
            cache_time, list_ = self._cache[list_id]
        except KeyError:
            # get the list from the inherited class
            return self.refreshCachedList(list_id)

        # check whether the cache needs refreshing
        if (time() - cache_time) > self.lifetime:
            return self.refreshCachedList(list_id)

        return list_

class MEDINVocabulary(CachedVocabulary):
    """
    Vocabulary object providing consistent API to all MEDIN vocabs

    Some MEDIN vocabularies are available via the vocabulary service,
    others are available as static lists. This object provides a
    common interface to all vocabs.
    """

    # the static lists
    static = {'resource-types': [
        {'defn': "Information applies to the attribute value",
         'abbr': "attribute",
         'term': "attribute"},
        {'defn': "Information applies to the characteristic of the feature",
         'abbr': "attributeType",
         'term': "attributeType"},
        {'defn': "Information applies to the collection hardware class",
         'abbr': "collectionHardware",
         'term': "collectionHardware"},
        {'defn': "Information applies to the collection session ",
         'abbr': "collectionSession",
         'term': "collectionSession"},
        {'defn': "Information applies to a single dataset.",
         'abbr': "dataset",
         'term': "dataset"},
        {'defn': "Information applies to a group of datasets linked by a common specification.",
         'abbr': "series",
         'term': "series"},
        {'defn': "Information applies to the non geographic dataset.",
         'abbr': "nonGeographicDataset",
         'term': "nonGeographicDataset"},
        {'defn': "Information applies to a dimension group",
         'abbr': "dimensionGroup",
         'term': "dimensionGroup"},
        {'defn': "Information applies to a feature",
         'abbr': "feature",
         'term': "feature"},
        {'defn': "Information applies to a feature type",
         'abbr': "featureType",
         'term': "featureType"},
        {'defn': "Information applies to a property type",
         'abbr': "propertyType",
         'term': "propertyType"},
        {'defn': "Information applies to a field session",
         'abbr': "fieldSession",
         'term': "fieldSession"},
        {'defn': "Information applies to a computer program or routine",
         'abbr': "software",
         'term': "software"},
        {'defn': "Information applies to a facility to view, download data e.g. web service",
         'abbr': "service",
         'term': "service"},
        {'defn': "Information applies to a copy  or imitation of an existing or hypothetical object",
         'abbr': "model",
         'term': "model"},
        {'defn': "Information applies to a tile, a spatial subset of geographic information",
         'abbr': "tile",
         'term': "tile"}],
              'access-types': [
        {'defn': "Exclusive right to the publication, production, or sale of the rights to a literary, dramatic, musical, or artistic work, or to the use of a commercial print or label, granted by law for a specified period of time to an author, composer, artist, distributor",
         'abbr': "copyright",
         'term': "copyright"},
        {'defn': "Government has granted exclusive right to make, sell, use or license an invention or discovery.",
         'abbr': "patent",
         'term': "patent"},
        {'defn': "Produced or sold information awaiting a patent.",
         'abbr': "patentPending",
         'term': "patentPending"},
        {'defn': "A name, symbol, or other device identifying a product, officially registered and legally restricted to the use of the owner or manufacturer.",
         'abbr': "trademark",
         'term': "trademark"},
        {'defn': "Formal permission required to do something.",
         'abbr': "license",
         'term': "license"},
        {'defn': "Rights to financial benefit from and control of distribution of non-tangible property that is a result of creativity.",
         'abbr': "intellectualPropertyRights",
         'term': "intellectualPropertyRights"},
        {'defn': "Withheld from general circulation or disclosure.",
         'abbr': "restricted",
         'term': "restricted"},
        {'defn': "Limitation not listed.",
         'abbr': "otherRestrictions",
         'term': "otherRestrictions"}]}

    def __init__(self, *args, **kwargs):
        lifetime = 3600           # seconds before a list is refreshed
        super(MEDINVocabulary, self).__init__(lifetime, *args, **kwargs)
        self.lists = {}

    def getStaticVocab(self, list_id):
        if list_id in self.static:
            try:
                return self.lists[list_id]
            except KeyError:
                vocab = self.lists[list_id] = StaticVocabList(self.static[list_id])
                return vocab
        raise KeyError('The list is not static: '+list_id)

    def lookupTerm(self, list_id, term):
        # try and get the list as a static vocabulary
        try:
            vocab = self.getStaticVocab(list_id)
        except KeyError:
            pass
        else:
            return vocab.lookupTerm(term)

        # get the list via SOAP
        return super(MEDINVocabulary, self).lookupTerm(list_id, term)

    def getList(self, list_id):
        # try and get the list as a static vocabulary
        try:
            vocab = self.getStaticVocab(list_id)
        except KeyError:
            pass
        else:
            return vocab.getList()

        # get the list via SOAP
        return super(MEDINVocabulary, self).getList(list_id)

class StaticVocabList(object):
    """
    An interface for accessing a static list
    """
    def __init__(self, vocab):
        self.vocab = vocab

    def lookupTerm(self, term):
        term = term.lower()
        try:
            entry = self.vocab[self.map[term]]
            return dict(long=entry['term'],
                        short=entry['abbr'],
                        defn=entry['defn'])
        except KeyError:
            raise LookupError('The term \'%s\' does not exist in the list' % term)
        except AttributeError:
            pass

        # the mapping does not exist; let's create it...
        self.map = {}
        for i, entry in enumerate(self.vocab):
            self.map[entry['abbr'].lower()] = i

        # ...and try again
        return self.lookupTerm(term)

    def getList(self):
        from copy import deepcopy
        return deepcopy(self.vocab)

