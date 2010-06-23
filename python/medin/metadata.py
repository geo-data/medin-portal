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

class MetadataError(Exception):
    def __init__(self, message, detail):
        self.message = message
        self.detail = detail

    def __str__(self):
        return self.message + ":\n" + self.detail

class ServiceError(MetadataError):
    pass

class Metadata(object):
    """Object model for MEDIN metadata

    Information is available in elements according to
    http://www.oceannet.org/marine_data_standards/medin_approved_standards/documents/medin_schema_documentation_2_3_2_10nov09.doc

    These elements are accessed via the object attributes and may
    themselves be compound objects.
    """
    
    title = None                        # element 1
    alt_titles = None                   # element 2
    abstract = None                     # element 3
    resource_type = None                # element 4
    online_resource = None              # element 5
    unique_id = None                    # element 6
    uid = None                          # id from the DWS
    coupled_resource = None             # element 7 TO BE IMPLEMENTED
    resource_language = None            # element 8
    topic_category = None               # element 9
    service_type = None                 # element 10
    keywords = None                     # element 11
    bbox = None                         # element 12
    extents = None                      # element 13
    vertical_extent = None              # element 14
    reference_system = None             # element 15
    temporal_reference = None           # element 16
    lineage = None                      # element 17
    spatial_resolution = None           # element 18
    additional_info = None              # element 19
    access_limits = None                # element 20
    access_conditions = None            # element 21
    responsible_party = None            # element 22
    data_format = None                  # element 23
    update_frequency = None             # element 24
    inspire_conformity = None           # element 25 TO BE IMPLEMENTED
    date = None                         # element 26
    name = None                         # element 27
    version = None                      # element 28
    language = None                     # element 29

    def __init__(self, uid):
        self.uid = uid

class HashSet(set):

    def __hash__(self):
        return reduce(lambda a, b: a | b, (hash(i) for i in self), 0)

class Contacts(object):

    def __init__(self, contacts):
        self.contacts = set(contacts)

    def matchAttribute(self, contact, attribute):
        def match(contact, attribute, attributes, matched):
            matches = set()
            for c in self.contacts:
                if id(c) in matched:
                    continue
                
                c_value = getattr(c, attribute)
                if c_value == getattr(contact, attribute) and c_value:
                    matches.add(c_value)
                    matched.add(id(c))
                if c == contact:
                    continue
                for attr in attributes:
                    if attr != attribute and getattr(c, attr) == getattr(contact, attr):
                        result = match(c, attribute, [a for a in attributes if a != attr], matched)
                        if result:
                            matches.update(result)
            return matches

        attributes = ('organisation', 'address', 'name', 'position', 'tel', 'fax', 'email')
        return tuple(match(contact, attribute, attributes, set()))

    def groupByOrganisation(self):
        return self.groupByAttribute('organisation')
    
    def groupByAddress(self):
        return self.groupByAttribute('address')

    def groupByTel(self):
        return self.groupByAttribute('tel')

    def groupByEmail(self):
        return self.groupByAttribute('email')

    def groupByFax(self):
        return self.groupByAttribute('fax')

    def groupByPosition(self):
        return self.groupByAttribute('position')

    def groupByName(self):
        return self.groupByAttribute('name')

    def groupByAttribute(self, attribute):
        from copy import deepcopy
        
        groups = {}
        for contact in self.contacts:
            contact = deepcopy(contact)
            value = getattr(contact, attribute)
            if not value:
                matches = self.matchAttribute(contact, attribute)
                if len(matches) == 1:
                    value = matches[0]
                else:
                    value = None
                setattr(contact, attribute, value)

            try:
                groups[value].contacts.add(contact)
            except KeyError:
                groups[value] = Contacts([contact])

        return groups

    def __str__(self):
        return "\n\n".join(map(str, self.contacts))

    def __iter__(self):
        return iter(self.contacts)

    def merge(self):
        contacts = []
        for organisation, groups in self.groupByOrganisation().items():
            num_people = groups.numberOfPeople()
            base = Contact(organisation)

            for contact in groups.contacts:
                if num_people > 2 and contact.isPerson():
                    attrs = ('organisation', 'address')
                    empty = False
                else:
                    empty = True
                    attrs = ('organisation', 'address', 'tel', 'fax', 'email', 'name', 'position')
                for attr in attrs:
                    baseval, curval = getattr(base, attr), getattr(contact, attr)
                    if curval:
                        if not baseval or curval == baseval:
                            setattr(base, attr, curval)
                            setattr(contact, attr, None)
                        else:
                            empty = False
                if empty:
                    base.roles.update(contact.roles)
                else:
                    base.addContact(contact)

            contacts.append(base)
            
        return Contacts(contacts)

    def numberOfPeople(self):
        count = 0
        for contact in self.contacts:
            if contact.isPerson(): count += 1

        return count

class Contact(object):

    organisation = None
    position = None
    name = None
    address = None
    email = None
    tel = None
    fax = None
    contacts = None
    roles = None
    
    def __init__(self, organisation):
        self.organisation = organisation
        self.contacts = HashSet()
        self.roles = HashSet()

    def __eq__(self, other):
        if id(self) == id(other):
            return True
        if self.position != other.position: return False
        elif self.name != other.name: return False
        elif self.address != other.address: return False
        elif self.organisation != other.organisation: return False
        elif self.contacts != other.contacts: return False
        elif self.roles != other.roles: return False
        elif self.email != other.email: return False
        elif self.tel != other.tel: return False
        elif self.fax != other.fax: return False
        else:
            return True

    def __hash__(self):        
        h = hash(''.join((str(getattr(self, attr)) for attr in ('address', 'name', 'position', 'tel', 'fax', 'email', 'organisation'))))
        return h | hash(self.contacts) | hash(self.roles)

    def isPerson(self):
        return self.name is not None or self.position is not None

    def sameContact(self, other):
        if self.position != other.position and self.position and other.position: return False
        elif self.name != other.name and self.name and other.name: return False
        elif self.address != other.address and self.address and other.address: return False
        elif self.organisation != other.organisation and self.organisation and other.organisation: return False
        elif self.email != other.email and self.email and other.email: return False
        elif self.tel != other.tel and self.tel and other.tel: return False
        elif self.fax != other.fax and self.fax and other.fax: return False
        else:
            return True

    def addContact(self, contact):
        for child in self.contacts:
            if child.sameContact(contact):
                child.contacts.update(contact.contacts)
                child.roles.update(contact.roles)
                return

        self.contacts.add(contact)
        
    def __str__(self):
        def serialise(contact, depth):
            s = []
            for attr in ('organisation', 'name', 'position', 'address', 'tel', 'fax', 'email'):
                val = getattr(contact, attr)
                if val:
                    s.append('%s: %s' % (attr.capitalize(), val))

            if contact.roles:
                roles = list(contact.roles)
                roles[0] = 'Roles: '+roles[0]
                for i in xrange(len(roles)-1):
                    roles[i+1] = '       '+roles[i+1]
                s.extend(roles)

            space = '  ' * depth
            sep = "\n" + space
            s = space + sep.join(s)

            depth += 2
            for child in contact.contacts:
                s += "\n\n" + serialise(child, depth)
                
            return s
        
        return serialise(self, 0)

# a decorator that ensures the xpath context is correct
def _assignContext(f):
    def newf(self):
        res = f(self)
        self.xpath.setContextNode(self.document)
        return res

    return newf

class Parser(object):
    """Parses MEDIN XML creating an object model

    Elements are parsed according to
    http://www.oceannet.org/marine_data_standards/medin_approved_standards/documents/medin_schema_documentation_2_3_2_10nov09.doc
    """
    
    def __init__(self, uid, document, areas):
        import re
        import libxml2
        from terms import MEDINVocabulary

        self.vocab = MEDINVocabulary() # instantiate the Vocabulary interface
        self.areas = areas
        self.uid = uid

        try:
            self.document = libxml2.parseMemory(document, len(document))
        except libxml2.parserError, e:
            raise ValueError('The metadata document could not be parsed: %s' % str(e))

        # register the namespaces we need to search
        xpath = self.xpath = self.document.xpathNewContext()
        xpath.xpathRegisterNs('gmd', 'http://www.isotc211.org/2005/gmd')
        xpath.xpathRegisterNs('gco', 'http://www.isotc211.org/2005/gco')
        xpath.xpathRegisterNs('srv', 'http://www.isotc211.org/2005/srv')
        xpath.xpathRegisterNs('xlink', 'http://www.w3.org/1999/xlink')
        xpath.xpathRegisterNs('gml', 'http://www.opengis.net/gml/3.2')

        self._keyword_pattern = re.compile('\s*([A-Z]\d+)\s*')

    def parse(self):
        m = Metadata(self.uid)
        m.title = self.title()          # element 1
        m.alt_titles = self.altTitles() # element 2
        m.abstract = self.abstract()    # element 3
        m.resource_type = self.resourceType() # element 4
        m.online_resource = self.onlineResource() # element 5
        m.unique_id = self.uniqueID()             # element 6
        # element 7 to be implemented...
        m.resource_language = self.resourceLanguage() # element 8
        m.topic_category = self.topicCategory()       # element 9
        m.service_type = self.serviceType()           # element 10
        m.keywords = self.keywords()                  # element 11
        m.bbox = self.bbox()                          # element 12
        m.extents = self.extents()                    # element 13
        m.vertical_extent = self.verticalExtent()     # element 14
        m.reference_system = self.referenceSystem()    # element 15
        m.temporal_reference = self.temporalReference() # element 16
        m.lineage = self.lineage()                      # element 17
        m.spatial_resolution = self.spatialResolution() # element 18
        m.additional_info =self.additionalInfo()        # element 19
        m.access_limits = self.accessLimits()           # element 20
        m.access_conditions = self.accessConditions()   # element 21
        m.responsible_party = self.responsibleParty()   # element 22
        m.data_format = self.dataFormat()               # element 23
        m.update_frequency = self.updateFrequency()     # element 24
        # element 25 to be implemented...
        m.date = self.date(False)       # element 26
        m.name = self.name()            # element 27
        m.version = self.version()      # element 28
        m.language = self.language()    # element 29
        
        return m

    def xsDate2pyDatetime(self, date):
        import datetime
        return datetime.datetime.strptime(date, '%Y-%m-%d')
        
    def xsDatetime2pyDatetime(self, timestamp):
        import datetime
        return datetime.datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%S')

    def author(self):
        try:
            return self.xpath.xpathEval("//gmd:CI_ResponsibleParty/gmd:role/gmd:CI_RoleCode[@codeListValue='originator']/../../gmd:organisationName/gco:CharacterString")[0].content.strip()
        except IndexError:
            return None

    # ELEMENTS ACCORDING TO THE MEDIN STANDARD:

    def title(self):
        """Element 1: Resource Title"""
        
        try:
            return self.xpath.xpathEval("//gmd:identificationInfo/gmd:MD_DataIdentification/gmd:citation/gmd:CI_Citation/gmd:title")[0].content.strip()
        except IndexError:
            return None

    def altTitles(self):
        """Element 2: Alternative Resource Title"""
        
        titles = []
        for node in self.xpath.xpathEval('//gmd:alternateTitle/gco:CharacterString/text()'):
            titles.append(node.content.strip())
        return titles

    def abstract(self):
        """Element 3: Resource Abstract"""
        
        try:
            return self.xpath.xpathEval("//gmd:identificationInfo/gmd:MD_DataIdentification/gmd:abstract")[0].content.strip()
        except IndexError:
            return None

    def resourceType(self):
        """Element 4: Resource Type"""
        from terms import VocabError
        
        try:
            code = self.xpath.xpathEval('//gmd:hierarchyLevel/gmd:MD_ScopeCode/text()')[0].content.strip()
        except IndexError:
            return None

        try:
            defn = self.vocab.lookupTerm('resource-types', code)
        except LookupError:
            defn = {'short':code,
                    'long':code,
                    'defn':'Unknown term'}
        except VocabError, e:
            defn = {'error': e.message}

        return defn

    @_assignContext
    def onlineResource(self):
        """Element 5: Resource Locator"""
        
        resources = []
        for node in self.xpath.xpathEval('//gmd:CI_OnlineResource'):
            resource = {}
            self.xpath.setContextNode(node)

            try:
                resource['link'] = self.xpath.xpathEval('./gmd:linkage/gmd:URL/text()')[0].content.strip()
            except IndexError:
                continue

            try:
                resource['name'] = self.xpath.xpathEval('./gmd:name/gmd:CharacterString/text()')[0].content.strip()
            except IndexError:
                resource['name'] = None

            try:
                resource['description'] = self.xpath.xpathEval('./gmd:description/gmd:CharacterString/text()')[0].content.strip()
            except IndexError:
                resource['description'] = None
            
            resources.append(resource)

        return resources

    def uniqueID(self):
        """Element 6: Unique Resourde Identifier"""
        
        for tag in ('MD_Identifier', 'RS_Identifier'):
            for node in self.xpath.xpathEval('//gmd:MD_DataIdentification//gmd:identifier/gmd:%s/gmd:code/gco:CharacterString/text()' % tag):
                return node.content.strip()
        return None

    # Element 7: Coupled Resource
    # To be implemented...

    def resourceLanguage(self):
        """Element 8: Resource Language"""
        
        langs = {'eng': 'English',
                 'cym': 'Welsh/Cymru',
                 'gle': 'Irish (Gaelic)',
                 'gla': 'Scottish (Gaelic)',
                 'cor': 'Cornish'}
        try:
            code = self.xpath.xpathEval('//gmd:MD_DataIdentification/gmd:language/gmd:LanguageCode/@codeListValue')[0].content.strip()
        except IndexError:
            return None

        try:
            return langs[code]
        except KeyError:
            try:
                code = self.xpath.xpathEval('//gmd:MD_DataIdentification/gmd:language/gmd:LanguageCode/text()')[0].content.strip()
            except IndexError:
                pass
            
        return code

    def topicCategory(self):
        """Element 9: Topic Category"""
        from terms import VocabError
        
        categories = {}
        for node in self.xpath.xpathEval('//gmd:MD_TopicCategoryCode/text()'):
            key = node.content.strip()
            try:
                defn = self.vocab.lookupTerm('P051', key)
            except LookupError:
                defn = {'short':key,
                        'long':key,
                        'defn':'Unknown term'}
            except VocabError, e:
                defn = {'error': e.message}
            categories[key] = defn

        return categories

    def serviceType(self):
        """Element 10: Spatial Data Service Type"""
        
        types = []
        for node in self.xpath.xpathEval('//srv:SV_ServiceIdentification/srv:serviceType/gco:LocalName/text()'):
            types.append(node.content.strip())
        return types

    @_assignContext
    def keywords(self):
        """Element 11: Keywords"""
        
        def keywordListFromTitle(title):
            """
            Parse a keyword title and return the list key if present

            e.g. the title "SeaDataNet BODC Vocabulary (P011)" returns
            P011. A case insensitive match is also done on the title for
            the string 'inspire', in which case the code P220 is
            returned.
            """

            if 'inspire' in title.lower():
                return 'P220'

            match = self._keyword_pattern.search(title)
            if not match:
                return None

            return match.groups()[0]

        from terms import VocabError
        
        keywords = {}
        for node in self.xpath.xpathEval('//gmd:descriptiveKeywords/gmd:MD_Keywords'):
            self.xpath.setContextNode(node)
            # try and retrieve the keywords
            try:
                words = [word.content.strip() for word in self.xpath.xpathEval('./gmd:keyword/gco:CharacterString/text()')]
            except IndexError:
                continue

            # try and get a code and a title for the list to which the
            # keywords belong
            try:
                code = self.xpath.xpathEval('.//gmd:MD_KeywordTypeCode/@codeListValue')[0].content.strip()
                title = code
            except IndexError:
                try:
                    title = self.xpath.xpathEval('.//gmd:title/gco:CharacterString/text()')[0].content.strip()
                except IndexError:
                    code = 'unknown'
                    title = code
                else:
                    code = keywordListFromTitle(title)

            for word in words:
                # try and get a definition for the term from the list code
                if code:
                    try:
                        defn = self.vocab.lookupTerm(code, word)
                    except LookupError:
                        defn = {'short':word,
                                'long':word,
                                'defn':'Unknown term'}
                    except VocabError, e:
                        defn = {'error': e.message}
                else:
                    defn = {}

                # add the definition to the keyword dictionary
                try:
                    keywords[title][word] = defn
                except KeyError:
                    defns = {word: defn}
                keywords[title] = defns

        return keywords

    @_assignContext
    def bbox(self):
        """Element 12: Geographic Bounding Box"""
        
        try:
            node = self.xpath.xpathEval('//gmd:EX_Extent/gmd:geographicElement/gmd:EX_GeographicBoundingBox')[0]
        except IndexError:
            return []
        self.xpath.setContextNode(node)
        
        ordinates = []

        for direction, latlon in (('west', 'longitude'), ('south', 'latitude'), ('east', 'longitude'), ('north', 'latitude')):
            try:
                
                ordinate = self.xpath.xpathEval('./gmd:%sBound%s/gco:Decimal/text()' % (direction, latlon.capitalize()))[0].content.strip()
            except IndexError:
                return []
            ordinates.append(float(ordinate))
            
        return ordinates

    @_assignContext
    def extents(self):
        """Element 13: Extent"""
        
        # mapping from citation title to area code
        code_map = {'Charting Progress 2 Sea Areas': 'cp',
                    'International Hydrographic Bureau, Limits of Oceans and Seas': 'sa'}
        
        extents = []
        for node in self.xpath.xpathEval('//gmd:geographicIdentifier/gmd:MD_Identifier'):
            self.xpath.setContextNode(node)
            try:
                title = self.xpath.xpathEval('./gmd:authority/gmd:CI_Citation/gmd:title/gco:CharacterString/text()')[0].content.strip()
            except IndexError:
                continue

            try:
                name = self.xpath.xpathEval('./gmd:code/gco:CharacterString/text()')[0].content.strip()
            except IndexError:
                continue

            try:
                code = code_map[title]
                area_id = self.areas.getAreaId(name, code)
            except KeyError:
                area_id = None

            extents.append(dict(title=title, name=name, id=area_id))
        return extents

    @_assignContext
    def verticalExtent(self):
        """Element 14: Vertical Extent Information"""
        
        try:
            node = self.xpath.xpathEval('//gmd:extent/gmd:EX_Extent/gmd:verticalElement/gmd:EX_VerticalExtent')[0]
        except IndexError:
            return None
        self.xpath.setContextNode(node)

        extents = {}
        for text, xpath in (('min-value', './gmd:minimumValue/gco:Real'),
                            ('max-value', './gmd:maximumValue/gco:Real'),
                            ('crs', './gmd:verticalCRS/@xlink:href')):
            try:
                content = self.xpath.xpathEval(xpath)[0].content.strip()
            except IndexError:
                continue
            extents[text] = content

        try:
            node = self.xpath.xpathEval('./gmd:verticalCRS/gml:VerticalCRS')[0]
        except IndexError:
            return extents
        self.xpath.setContextNode(node)

        try:
            code = self.xpath.xpathEval('./gml:identifier/@codeSpace')[0].content.strip()
            idf = self.xpath.xpathEval('./gml:identifier/text()')[0].content.strip()
            extents['crs-id'] = (code, idf)
        except IndexError:
            pass

        try:
            name = self.xpath.xpathEval('./gml:name')[0].content.strip()
        except IndexError:
            pass
        else:
            extents['crs-name'] = name

        try:
            scope = self.xpath.xpathEval('./gml:scope')[0].content.strip()
        except IndexError:
            pass
        else:
            extents['crs-scope'] = scope

        try:
            code = self.xpath.xpathEval('./gml:verticalCS/gml:VerticalCS/gml:identifier/@codeSpace')[0].content.strip()
            idf = self.xpath.xpathEval('./gml:verticalCS/gml:VerticalCS/gml:identifier/text()')[0].content.strip()
            extents['cs-id'] = (code, idf)
        except IndexError:
            pass

        try:
            name = self.xpath.xpathEval('./gml:verticalCS/gml:VerticalCS/gml:name')[0].content.strip()
        except IndexError:
            pass
        else:
            extents['cs-name'] = name

        try:
            code = self.xpath.xpathEval('./gml:verticalCS/gml:VerticalCS/gml:axis/gml:CoordinateSystemAxis/gml:identifier/@codeSpace')[0].content.strip()
            idf = self.xpath.xpathEval('./gml:verticalCS/gml:VerticalCS/gml:axis/gml:CoordinateSystemAxis/gml:identifier/text()')[0].content.strip()
            extents['csaxis-id'] = (code, idf)
        except IndexError:
            pass

        try:
            abbrev = self.xpath.xpathEval('./gml:verticalCS/gml:VerticalCS/gml:axis/gml:CoordinateSystemAxis/gml:axisAbbrev/text()')[0].content.strip()
            direction = self.xpath.xpathEval('./gml:verticalCS/gml:VerticalCS/gml:axis/gml:CoordinateSystemAxis/gml:axisDirection/text()')[0].content.strip()
            extents['csaxis-info'] = (abbrev, direction)
        except IndexError:
            pass
        
        try:
            code = self.xpath.xpathEval('./gml:verticalDatum/gml:VerticalDatum/gml:identifier/@codeSpace')[0].content.strip()
            idf = self.xpath.xpathEval('./gml:verticalDatum/gml:VerticalDatum/gml:identifier/text()')[0].content.strip()
            extents['datum-id'] = (code, idf)
        except IndexError:
            pass

        try:
            name = self.xpath.xpathEval('./gml:verticalDatum/gml:VerticalDatum/gml:name')[0].content.strip()
        except IndexError:
            pass
        else:
            extents['datum-name'] = name

        try:
            scope = self.xpath.xpathEval('./gml:verticalDatum/gml:VerticalDatum/gml:scope')[0].content.strip()
        except IndexError:
            pass
        else:
            extents['datum-scope'] = scope

        try:
            defn = self.xpath.xpathEval('./gml:verticalDatum/gml:VerticalDatum/gml:anchorDefinition')[0].content.strip()
        except IndexError:
            pass
        else:
            extents['datum-info'] = defn

        return extents

    def referenceSystem(self):
        """Element 15: Spatial Reference System"""
        
        # get the SRS code
        try:
            code = self.xpath.xpathEval('//gmd:referenceSystemInfo/gmd:MD_ReferenceSystem/gmd:referenceSystemIdentifier/gmd:RS_Identifier/gmd:code/gco:CharacterString/text()')[0].content.strip()
        except IndexError:
            return MetadataError('Unknown spatial reference system', 'The spatial reference system could not be extracted from the metadata')

        # get the XML corresponding to the code from the EPSG
        from urllib2 import urlopen, URLError, HTTPError
        epsg_url = 'http://www.epsg-registry.org/export.htm?gml=%s' % code

        try:
            res = urlopen(epsg_url, timeout=5)
        except HTTPError, e:
            return MetadataError('The spatial reference system information could not be obtained',
                                 'The URL at %s could not be opened: %s' % (epsg_url, str(e)))
        except URLError, e:
            try:
                status, msg = e.reason
            except ValueError:
                msg = str(e.reason)

            return MetadataError('The spatial reference system information could not be obtained',
                                 'The URL at %s could not be opened: %s' % (epsg_url, msg))

        content_type = res.headers['content-type'].split(';')[0]
        if content_type != 'text/xml':
            return MetadataError('The spatial reference system information could not be obtained',
                                 'The resource at %s is not valid XML' % epsg_url)
        
        xml = res.read()

        # parse the XML
        import libxml2
        try:
            document = libxml2.parseMemory(xml, len(xml))
        except libxml2.parserError, e:
            return MetadataError('The spatial reference system information could not be obtained',
                                 'The reference system XML at %s could not be parsed: %s' % (epsg_url, str(e)))

        # register the namespaces we need to search
        xpath = document.xpathNewContext()
        xpath.xpathRegisterNs('gml', 'http://www.opengis.net/gml')

        details = {'identifier': code,
                   'source': 'European Petroleum Survey Group (EPSG)',
                   'url': epsg_url}
        try:
            name = xpath.xpathEval('//gml:*/gml:name')[0].content.strip()
            details['name'] = name
        except IndexError:
            details['name'] = None

        try:
            scope = xpath.xpathEval('//gml:*/gml:scope')[0].content.strip()
            details['scope'] = scope
        except IndexError:
            details['scope'] = None

        return details

    @_assignContext
    def temporalReference(self):
        """Element 16: Temporal Reference"""
        
        dates = {}
        try:
            begin = self.xpath.xpathEval('//gmd:EX_Extent/gmd:temporalElement/gmd:EX_TemporalExtent//gml:beginPosition')[0].content.strip()
            end = self.xpath.xpathEval('//gmd:EX_Extent/gmd:temporalElement/gmd:EX_TemporalExtent//gml:endPosition')[0].content.strip()
        except IndexError:
            pass
        else:
            try:
                dates['range'] = [self.xsDate2pyDatetime(begin), self.xsDate2pyDatetime(end)]
            except ValueError:
                pass

        single = []
        for node in self.xpath.xpathEval('//gmd:MD_DataIdentification/gmd:citation/gmd:CI_Citation/gmd:date/gmd:CI_Date'):
            self.xpath.setContextNode(node)
            try:
                date = self.xpath.xpathEval('./gmd:date/gco:Date')[0].content.strip()
            except IndexError:
                continue

            try:
                code = self.xpath.xpathEval('./gmd:dateType/gmd:CI_DateTypeCode')[0].content.strip()
            except IndexError:
                continue

            try:
                date = self.xsDate2pyDatetime(date)
            except ValueError:
                continue
            
            single.append((code, date))

        if single:
            dates['single'] = single

        return dates

    def lineage(self):
        """Element 17: Lineage"""
        
        try:
            lineage = self.xpath.xpathEval('//gmd:lineage/gmd:LI_Lineage/gmd:statement/gco:CharacterString')[0].content.strip()
        except IndexError:
            return None

        return lineage

    @_assignContext
    def spatialResolution(self):
        """Element 18: Spatial Resolution"""
        
        details = []
        for node in self.xpath.xpathEval('//gmd:MD_DataIdentification/gmd:spatialResolution/gmd:MD_Resolution'):
            self.xpath.setContextNode(node)

            entry = {}
            try:
                distance = self.xpath.xpathEval('./gmd:distance/gco:Distance')[0].content.strip()
            except IndexError:
                pass
            else:
                entry['distance'] = distance

            try:
                scale = self.xpath.xpathEval('./gmd:equivalentScale/gmd:MD_RepresentativeFraction/gmd:denominator')[0].content.strip()
            except IndexError:
                pass
            else:
                entry['scale'] = scale

            if entry:
                details.append(entry)

        return details

    def additionalInfo(self):
        """Element 19: Additional Information Source"""
        
        try:
            info = self.xpath.xpathEval('//gmd:MD_DataIdentification/gmd:supplementalInformation/gco:CharacterString')[0].content.strip()
        except IndexError:
            return None

        return info

    def accessLimits(self):
        """Element 20: Limitations On Public Access"""
        from terms import VocabError
        
        limits = []
        for node in self.xpath.xpathEval('//gmd:MD_DataIdentification/gmd:resourceConstraints/gmd:MD_LegalConstraints/gmd:accessConstraints/gmd:MD_RestrictionCode'):
            key = node.content.strip()
            try:
                defn = self.vocab.lookupTerm('access-types', key)
            except LookupError:
                defn = {'short':key,
                        'long':key,
                        'defn':'Unknown term'}
            except VocabError, e:
                defn = {'error': e.message}
            limits.append(defn)

        for node in self.xpath.xpathEval('//gmd:MD_DataIdentification/gmd:resourceConstraints/gmd:MD_LegalConstraints/gmd:otherConstraints'):
            limits.append({'other': node.content.strip()})

        return limits

    def accessConditions(self):
        """Element 21: Conditions Applying For Access And Use"""
        
        details = []
        for node in self.xpath.xpathEval('//gmd:MD_DataIdentification/gmd:resourceConstraints/gmd:*/gmd:useLimitation'):
            details.append(node.content.strip())

        return details

    @_assignContext
    def responsibleParty(self):
        """Element 22: Responsible Party"""
        
        xpaths = ('//gmd:MD_Metadata/gmd:contact/gmd:CI_ResponsibleParty',
                  '//gmd:MD_Metadata/gmd:identificationInfo/gmd:MD_DataIdentification/gmd:pointOfContact/gmd:CI_ResponsibleParty',
                  '//gmd:MD_Metadata/gmd:distributionInfo/gmd:MD_Distribution/gmd:distributor/gmd:MD_Distributor/gmd:distributorContact/gmd:CI_ResponsibleParty')
        parties = []
        for xpath in xpaths:
            for node in self.xpath.xpathEval(xpath):
                contact = self._contactDetails(node)
                parties.append(contact)

        contacts = Contacts(parties)
        return contacts.merge()

    def _contactDetails(self, node):
        roles = {'resourceProvider': 'Party that supplies the resource.',
                 'custodian': 'Party that accepts accountability and responsibility for the data and ensures appropriate care and maintenance of the resource.',
                 'owner': 'Party that owns the resource.',
                 'user': 'Party who uses the resource.',
                 'distributor': 'Party that distributes the resource.',
                 'originator': 'Party who created the resource.',
                 'pointOfContact': 'Party who can be contacted for acquiring knowledge about or acquisition of the resource.',
                 'principalInvestigator': 'Key party responsible for gathering information and conducting research.',
                 'processor': 'Party who has processed the data in a manner such that the resource has been modified.',
                 'publisher': 'Party who published the resource.',
                 'author': 'Party who authored the resource.'}
        
        self.xpath.setContextNode(node)

        try:
            organisation = self.xpath.xpathEval('./gmd:organisationName')[0].content.strip()
        except IndexError:
            organisation = None

        contact = Contact(organisation)

        try:
            contact.name = self.xpath.xpathEval('./gmd:individualName')[0].content.strip()
        except IndexError:
            pass

        try:
            contact.position = self.xpath.xpathEval('./gmd:positionName')[0].content.strip()
        except IndexError:
            pass
        
        address = []
        for node in self.xpath.xpathEval('./gmd:contactInfo/gmd:CI_Contact/gmd:address/gmd:CI_Address/gmd:deliveryPoint'):
            address.append(node.content.strip())

        for tag in ('city', 'postalCode', 'country'):
            try:
                res = self.xpath.xpathEval('./gmd:contactInfo/gmd:CI_Contact/gmd:address/gmd:CI_Address/gmd:%s' % tag)[0].content
                address.append(res.strip())
            except IndexError:
                pass

        if address:
            contact.address = ', '.join(address)

        try:
            contact.tel = self.xpath.xpathEval('./gmd:contactInfo/gmd:CI_Contact/gmd:phone/gmd:CI_Telephone/gmd:voice')[0].content.strip()
        except IndexError:
            pass

        try:
            contact.fax = self.xpath.xpathEval('./gmd:contactInfo/gmd:CI_Contact/gmd:phone/gmd:CI_Telephone/gmd:facsimile')[0].content.strip()
        except IndexError:
            pass

        try:
            email = self.xpath.xpathEval('./gmd:contactInfo/gmd:CI_Contact/gmd:address/gmd:CI_Address/gmd:electronicMailAddress')[0].content.strip()
        except IndexError:
            pass
        else:
            contact.email = email.replace('@', '(at)').replace('.', '(dot)') # obfuscate the address

        try:
            role = self.xpath.xpathEval('./gmd:role/gmd:CI_RoleCode')[0].content.strip()
        except IndexError:
            pass
        else:
            try:
                contact.roles.add(roles[role])
            except KeyError:
                contact.roles.add(role)

        return contact

    @_assignContext
    def dataFormat(self):
        """Element 23: Data Format"""
        from terms import VocabError
        
        formats = {}
        for node in self.xpath.xpathEval('//gmd:MD_DataIdentification/gmd:resourceFormat/gmd:MD_Format'):
            self.xpath.setContextNode(node)
            try:
                key = self.xpath.xpathEval('./gmd:name/gco:CharacterString')[0].content.strip()
            except KeyError:
                continue

            try:
                defn = self.vocab.lookupTerm('M010', key)
            except LookupError:
                defn = {'short':key,
                        'long':key,
                        'defn':'Unknown term'}
            except VocabError, e:
                defn = {'error': e.message}
            formats[key] = defn

        return formats

    def updateFrequency(self):
        """Element 24: Frequency of Update"""
        
        codes = {'continual': 'Data is repeatedly and frequently updated',
                 'daily': 'Data is updated each day',
                 'weekly': 'Data is updated on a weekly basis',
                 'fortnightly': 'Data is updated every two weeks',
                 'monthly': 'Data is updated each month',
                 'quarterly': 'Data is updated every three months',
                 'biannually': 'Data is updated twice each year',
                 'annually': 'Data is updated every year',
                 'asNeeded': 'Data is updated as deemed necessary',
                 'irregular': 'Data is updated at intervals that are uneven in duration',
                 'notPlanned': 'There are no plans to update the data',
                 'unknown': 'Frequency of maintenance for the data is not known'}

        try:
            code = self.xpath.xpathEval('//gmd:MD_DataIdentification/gmd:resourceMaintenance/gmd:MD_MaintenanceInformation/gmd:maintenanceAndUpdateFrequency/gmd:MD_MaintenanceFrequencyCode/@codeListValue')[0].content.strip()
        except IndexError:
            return None

        try:
            return codes[code]
        except KeyError:
            return code

    # Element 25: Inspire Conformity
    # To be implemented...

    def date(self, raise_error=True):
        """Element 26: Metadata Date"""
        try:
            date = self.xpath.xpathEval('/gmd:MD_Metadata/gmd:dateStamp/gco:Date')[0].content.strip()
        except IndexError:
            pass
        else:
            try:
                return self.xsDate2pyDatetime(date)
            except ValueError, e:
                exception = MetadataError('The metadata date is not valid',
                                          'The date retrieved from the XML is not a valid date: %s' % date)
                if raise_error:
                    raise exception
                return exception

        try:
            datetime = self.xpath.xpathEval('/gmd:MD_Metadata/gmd:dateStamp/gco:DateTime')[0].content.strip()
        except IndexError:
            return None
        try:
            return self.xsDatetime2pyDatetime(datetime)
        except ValueError, e:
            exception = MetadataError('The metadata timestamp is not valid',
                                      'The timestamp retrieved from the XML is not a valid datetime: %s' % date)
            if raise_error:
                raise exception
            return exception

    def name(self):
        """Element 27: Metadata Standard Name"""
        
        try:
            return self.xpath.xpathEval('//gmd:MD_Metadata/gmd:metadataStandardName/gco:CharacterString')[0].content.strip()
        except IndexError:
            return None

    def version(self):
        """Element 28: Metadata Standard Version"""
        
        try:
            return self.xpath.xpathEval('//gmd:MD_Metadata/gmd:metadataStandardVersion/gco:CharacterString')[0].content.strip()
        except IndexError:
            return None
            
    def language(self):
        """Element 29: Metadata Language"""
        
        try:
            return self.xpath.xpathEval('//gmd:MD_Metadata/gmd:language/gmd:LanguageCode')[0].content.strip()
        except IndexError:
            return None

if __name__ == '__main__':
    c1 = Contact('Marine Biological Association of the UK (MBA)')
    c1.address = 'The Laboratory, Citadel Hill'
    c1.email = 'sec@mba.ac.uk'
    c1.roles.add('pointOfContact')

    c2 = Contact(None)
    c2.name = 'N. A. Anwar'
    c2.tel = '01752 633207'
    c2.email = 'sec@mba.ac.uk'
    c2.roles.add('originator')

    c3 = Contact('Marine Biological Association of the UK (MBA)')
    c3.position = 'Biological Record Officer'
    c3.tel = '+44 1752 633291'
    c3.address = 'The Laboratory, Citadel Hill'
    c3.email = 'sec@mba.ac.uk'
    c3.roles.add('custodian')

    c4 = Contact('Marine Biological Association of the UK (MBA)')
    c4.position = 'Biological Record Officer'
    c4.tel = '+44 1752 633291'
    c4.address = 'The Laboratory, Citadel Hill'
    c4.email = 'sec@mba.ac.uk'
    c4.roles.add('distributor')

    contacts = Contacts([c1, c2, c3, c4])

    print "Original Contacts:"
    print contacts

    print "\nMerged Contacts:"
    print contacts.merge()
