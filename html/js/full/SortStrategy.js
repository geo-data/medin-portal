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
* @requires OpenLayers/Strategy.js
*/

/**
* Class: SortStrategy
* Strategy for vector feature sorting.
*
* Inherits from:
* - <OpenLayers.Strategy>
*/
SortStrategy = OpenLayers.Class(OpenLayers.Strategy, {
    
    /**
* APIProperty: cmp
* {Function} A comparison function that determines the sorting. This
* function accepts two features to compare as arguments and returns an
* integer.
*/
    cmp: null,

    /**
* Property: sorting
* {Boolean} The strategy is currently sorting features.
*/
    sorting: false,

    /**
* Constructor: SortStrategy
* Create a new clustering strategy.
*
* Parameters:
* options - {Object} Optional object whose properties will be set on the
* instance.
*/
    
    /**
* APIMethod: activate
* Activate the strategy. Register any listeners, do appropriate setup.
*
* Returns:
* {Boolean} The strategy was successfully activated.
*/
    activate: function() {
        var activated = OpenLayers.Strategy.prototype.activate.call(this);
        if(activated) {
            this.layer.events.on({
                "beforefeaturesadded": this.sortFeatures,
                scope: this
            });
        }
        return activated;
    },
    
    /**
* APIMethod: deactivate
* Deactivate the strategy. Unregister any listeners, do appropriate
* tear-down.
*
* Returns:
* {Boolean} The strategy was successfully deactivated.
*/
    deactivate: function() {
        var deactivated = OpenLayers.Strategy.prototype.deactivate.call(this);
        if(deactivated) {
            this.clearCache();
            this.layer.events.un({
                "beforefeaturesadded": this.sortFeatures,
                scope: this
            });
        }
        return deactivated;
    },
    
    /**
* Method: sortFeatures
* Sort features before they are added to the layer.
*
* Parameters:
* event - {Object} The event that this was listening for. This will come
* with a batch of features to be sorted.
*
* Returns:
* {Boolean} False to stop features from being added to the layer.
*/
    sortFeatures: function(event) {
        var propagate = true,
            features;
        if(!this.sorting) {
            this.sorting = true;
            features = this.sort(event.features);
            this.layer.addFeatures(features);
            this.sorting = false;
            propagate = false;
        }
        return propagate;
    },
    
    /**
* Method: sort
* Sort features based on the user specified function
*
* Parameters:
* features - {Array} The features to be sorted
*/
    sort: function(features) {
        features.sort(this.cmp);
        return features;
    },
    
    CLASS_NAME: "SortStrategy"
});
