/*
 * Created by Homme Zwaagstra
 * 
 * Copyright (c) 2010 GeoData Institute
 * http://www.geodata.soton.ac.uk
 * geodata@soton.ac.uk
 * 
 * Unless explicitly acquired and licensed from Licensor under another
 * license, the contents of this file are subject to the Reciprocal
 * Public License ("RPL") Version 1.5, or subsequent versions as
 * allowed by the RPL, and You may not copy or use this file in either
 * source code or executable form, except in compliance with the terms
 * and conditions of the RPL.
 * 
 * All software distributed under the RPL is provided strictly on an
 * "AS IS" basis, WITHOUT WARRANTY OF ANY KIND, EITHER EXPRESS OR
 * IMPLIED, AND LICENSOR HEREBY DISCLAIMS ALL SUCH WARRANTIES,
 * INCLUDING WITHOUT LIMITATION, ANY WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE, QUIET ENJOYMENT, OR
 * NON-INFRINGEMENT. See the RPL for specific language governing rights
 * and limitations under the RPL.
 * 
 * You can obtain a full copy of the RPL from
 * http://opensource.org/licenses/rpl1.5.txt or geodata@soton.ac.uk
 */

/**
* @requires OpenLayers/Filter.js
*/

/**
* @class ContainsFilter
*
* This class represents a spatial filter whereby features must be
* contained within the bounding box specified as the 'type'.
*
* Inherits from:
* - <OpenLayers.Filter>
*/
ContainsFilter = OpenLayers.Class(OpenLayers.Filter, {

    /**
* APIProperty: bounds
* {<OpenLayers.Bounds>} The bounding box used for testing
*/
    bounds: null,
    
    /**
* Constructor: ContainsFilter
* Creates a spatial filter.
*
* Parameters:
* options - {Object} An optional object with properties to set on the
* filter.
*
* Returns:
* {<ContainsFilter>}
*/

   /**
* Method: evaluate
* Evaluates this filter for a specific feature.
*
* Parameters:
* feature - {<OpenLayers.Feature.Vector>} feature to apply the filter to.
*
* Returns:
* {Boolean} The feature meets filter criteria.
*/
    evaluate: function(feature) {
        var contains = false;
        if (this.bounds && (feature.bounds || feature.geometry)) {
            contains = this.bounds.containsBounds(
                bounds = feature.bounds || feature.geometry.getBounds(),
                false,
                false
            );
        }
        return contains;
    },

    /**
* APIMethod: clone
* Clones this filter.
*
* Returns:
* {<OpenLayers.Filter.Spatial>} Clone of this filter.
*/
    clone: function() {
        var options = OpenLayers.Util.applyDefaults({
            bounds: this.bounds && this.bounds.clone && this.bounds.clone()
        }, this);
        return new ContainsFilter(options);
    },
    CLASS_NAME: "ContainsFilter"
});
