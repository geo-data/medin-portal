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

from docutils import core

"""
Filters used in Mako templates.

This module is imported as required by the appropriate template.
"""

def quote(text):
    """
    Wrap text in double quotes if the text contains a space.

    This is designed to be used as a mako filter expression.
    """
    if ' ' in text:
        return '"' + text + '"'
    return text

def rst2html(rst):
    """Convert restructured text into a HTML fragment"""
    # taken from <https://wiki.python.org/moin/ReStructuredText>

    parts = core.publish_parts(source=rst, writer_name='html')
    return parts['body_pre_docinfo']+parts['fragment']
