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

// initialise the map when the fieldset is first clicked
function init_spatial(results_url) {
    $(document).one('fieldsetview', function onFieldsetview(id) {
        init_results_map(results_url);
        // make the map full width
        $('#map').css('width', '100%');
        map.updateSize();
    });
}

// top level function to initialise the map
function init_results_map(results_url) {
    var nav = init_map(),                 // the base map initialisation
        select,
        kml,
        filter,
        filterStrategy,
        sortStrategy;

    filter = new ContainsFilter({
        bounds: map.getMaxExtent()
    });
    filterStrategy = new OpenLayers.Strategy.Filter({filter: filter});

    // a sort strategy to sort by area so that the largest areas are
    // rendered below the smallest, allowing the smallest to be
    // clicked on.
    sortStrategy = new SortStrategy({
        cmp: function cmp(a, b) {
            return b.geometry.getArea() - a.geometry.getArea();
        }
    });
    
    kml = new OpenLayers.Layer.Vector("Results", {
        strategies: [new OpenLayers.Strategy.Fixed(), filterStrategy, sortStrategy],
        protocol: new OpenLayers.Protocol.HTTP({
            url: results_url,
            format: new OpenLayers.Format.KML({
                extractStyles: true, 
                extractAttributes: true,
                kmlns: '2.2'
            })
        })
    });

    map.addLayer(kml);

    // add popup functionality (adapted from http://www.openlayers.org/dev/examples/sundials.html)
    select = new OpenLayers.Control.SelectFeature(kml);
    
    kml.events.on({
        "featureselected": onFeatureSelect,
        "featureunselected": onFeatureUnselect,
        "loadend": function onLoadEnd(event) {
            // zoom to the extent of the data once it is loaded
            map.zoomToExtent(kml.getDataExtent());
        }
    });

    map.addControl(select);
    select.activate();   

    map.zoomToMaxExtent();

    function onPopupClose(evt) {
        select.unselectAll();
    }
    function onFeatureSelect(event) {
        var feature = event.feature;
        // Since KML is user-generated, do naive protection against
        // Javascript.
        var content = "<h2>"+feature.attributes.name + "</h2>" + feature.attributes.description;
        if (content.search("<script") != -1) {
            content = "Content contained Javascript! Escaped content below.<br>" + content.replace(/</g, "&lt;");
        }
        popup = new OpenLayers.Popup.FramedCloud(
            "chicken", 
            feature.geometry.getBounds().getCenterLonLat(),
            new OpenLayers.Size(100,100),
            content,
            null, true, onPopupClose
        );
        feature.popup = popup;
        map.addPopup(popup);
    }
    function onFeatureUnselect(event) {
        var feature = event.feature;
        if(feature.popup) {
            map.removePopup(feature.popup);
            feature.popup.destroy();
            delete feature.popup;
        }
    }
}
