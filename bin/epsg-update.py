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

from sys import stderr
import argparse
from os.path import abspath
from epsg import Registry
from sqlalchemy import create_engine

def main():
    """
    Update the local registry
    """

    parser = argparse.ArgumentParser(description='Update the EPSG SQLite database from the online registry.')
    parser.add_argument('file', metavar='FILE', nargs=1,
                        help='The SQLite database file to update')
    args = parser.parse_args()
    filename = abspath(args.file[0])
    try:
        engine = create_engine('sqlite:///%s' % filename)
        # create an empty Registry if it is not already populated
        registry = Registry(engine, loader=False)
        registry.init(loader=False) # re-initialise the database
        loader = registry.getLoader()
        registry.update(loader)
        del registry
        del engine
    except KeyboardInterrupt:
        print >> stderr, "\nInterrupted!"
        
if __name__ == '__main__':
    main()
