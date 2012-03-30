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

from epsg import Registry
from sqlalchemy import create_engine
import os.path

_registry = None
def resolve(code):
    """
    Resolve an EPSG code to an object
    """

    global _registry
    try:
        return _registry[code]
    except TypeError:
        pass

    path = os.path.join(os.path.dirname(__file__), os.path.pardir, os.path.pardir, 'data', 'epsg-registry.sqlite')
    engine = create_engine('sqlite:///%s' % path)
    _registry = Registry(engine)
    return _registry.get(code, None)
