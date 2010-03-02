"""
Module for connecting to and querying the SeaDataNet Common Vocabularies Web Service

The module uses the WS SOAP interface. Further details are available at:

- http://www.seadatanet.org/standards_software/common_vocabularies
- http://www.bodc.ac.uk/products/web_services/vocab/
"""

import os
import suds

class Vocabulary(object):
    
    def __init__(self, wsdl=None):
        if wsdl is None:
            # from http://www.bodc.ac.uk/extlink/http%3A//vocab.ndg.nerc.ac.uk/1.1/VocabServerAPI_dl.wsdl
            wsdl = 'file://%s' % os.path.abspath(os.path.join(os.path.dirname(__file__), 'data', 'VocabServerAPI_dl.wsdl'))

        self.client = suds.client.Client(wsdl)

    def lookupTerm(self, list, term):
        """
        Return the definition of a term based on the entry key term

        If the term does not match the 'short' entry key, then the
        'long' entry key is tried instead.
        """
        
        listKey = 'http://vocab.ndg.nerc.ac.uk/list/%s/current' % list
        r = self.client.service.verifyTerm(listKey, term, 'short')
        try:
            term = r.verifiedTerm
        except AttributeError:
            # try looking up the term as a 'long' entry
            r = self.client.service.verifyTerm(listKey, term, 'long')
            try:
                term = r.verifiedTerm
            except AttributeError:
                raise LookupError('The term "%s" does not exist in the list %s' % (term, listKey))

        return dict(long=term.entryTerm,
                    short=term.entryTermAbbr,
                    defn=term.entryTermDef)
