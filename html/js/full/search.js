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

// how long before loading messages should be displayed in milliseconds
var LOAD_DELAY = 1000;

// jQuery CSS map determining the style of the area box
var BOX_SELECTED = {
    'background-color': 'transparent',
    'border-color': '#0B8AB3',
    'border-width': '2px',
    'border-style': 'solid',
    'background-image': "url('/images/area-fill-selected.png')",
    'background-repeat': 'repeat'
};

var BOX_DESELECTED = {
    'background-color': 'transparent',
    'border-color': '#CA0000',
    'border-width': '2px',
    'border-style': 'solid',
    'background-image': "url('/images/area-fill.png')",
    'background-repeat': 'repeat'
};

// top level function to initialise the map
function init_map() {
    var extent = new OpenLayers.Bounds(-180, -90, 180, 90);
    var options = {
        restrictedExtent: extent,
        maxExtent: extent,
        maxResolution: 360/512,
        controls: []            // we will add our own controls
    }

    map = new OpenLayers.Map('map', options); // assign the map to the global variable

    // add the bathymetry layer
    var layer = new OpenLayers.Layer.TMS( "Bathy",
                                      script_root+'/spatial/tms/',
                                      { layername: 'bathymetry',
                                        type: 'png',
                                        displayInLayerSwitcher: false } );
    map.addLayer(layer);

    // add the UK Charting Progress Sea Areas
    var styleMap = new OpenLayers.StyleMap({
        'default': OpenLayers.Util.applyDefaults(
            {
                label: '${Name}',
                fontColor: '#1E2772',
                strokeWidth:1,
                strokeColor:"#52577C",
                fillColor: "blue",
                fillOpacity: 0.25
            })
    });

    var layer = new OpenLayers.Layer.GML( "UK Charting Progress Sea Areas",
                                          '/data/charting-progress/areas.geojson',
                                          {
                                              styleMap: styleMap,
                                              visibility: false,
                                              format: OpenLayers.Format.GeoJSON
                                          });
    map.addLayer(layer);

    // add the ICES rectangles layer. This is a subset of data from the DASS WFS
    styleMap = new OpenLayers.StyleMap({
        'default': OpenLayers.Util.applyDefaults(
            {
                label: '${Name}', // ${dassh:ICESNAME} when using DASSH WFS
                fontColor: '#72721E',
                strokeWidth:1,
                strokeColor:"#7C7B52",
                fillColor: "yellow",
                fillOpacity: 0.25
            })
    });

    layer = new OpenLayers.Layer.GML( "ICES Rectangles",
                                      '/data/ices-rectangles/areas.geojson',
                                      {
                                          styleMap: styleMap,
                                          format: OpenLayers.Format.GeoJSON,
                                          visibility: false,
                                          minScale: 3500000
                                      });
    /* OpenLayers in FireFox doesn't seem to like the DASSH WFS
    layer = new OpenLayers.Layer.WFS( "ICES Rectangles",
                                      "http://www.dassh.ac.uk:8081/geoserver/wfs?",
                                      {
                                          typename: "dassh:ices_squares_simple",
                                          maxfeatures: 100
                                      },
                                      {
                                          featureClass: OpenLayers.Feature.WFS,
                                          minScale: 3500000,
                                          styleMap: styleMap
                                      });*/
    map.addLayer(layer);

    // default controls
    var nav = new OpenLayers.Control.Navigation();
    map.addControl(nav);
    map.addControl(new OpenLayers.Control.PanZoom());
    map.addControl(new OpenLayers.Control.ArgParser());
    map.addControl(new OpenLayers.Control.Attribution());
    map.addControl(new OpenLayers.Control.LayerSwitcher());

    // the graticule layer
    map.addControl(new OpenLayers.Control.Graticule({
        numPoints: 2, 
        labelled: true,
        visible: true
    }));

    map.addControl(new OpenLayers.Control.MousePosition());
    
    // the layer to contain the area box
    var boxes = new OpenLayers.Layer.Boxes("boxes", { displayInLayerSwitcher: false });
    map.addLayer(boxes);

    // the custom control to draw area boxes
    var control = map.box_control = new OpenLayers.Control.BoxDraw();
    control.box_layer = boxes;
    map.addControl(control);
    control.activate();

    // ensure navigation is deactivated when the CTRL key is pressed
    // or the box is selected, otherwise it interferes with the box
    // drawing.
    $(document).keydown(function(evt) {
        // only deactivate if it's the CTRL key and the nav is active
        if (evt.which == 17 && nav.active) {
            nav.deactivate();
            $(this).data('deactivated', true);
        }
        // deactivate the box drawing if SHIFT is pressed
        else if (evt.which == 16 && control.active) {
            control.deactivate();
        }
    }).keyup(function(evt) {
        var self = $(this);
        // only activate if previously deactivated by this code
        if (evt.which == 17 && self.data('deactivated')) {  // it's the CTRL key
            nav.activate();
            self.data('deactivated', false);
        }
        // re-activate the box drawing when SHIFT is released
        else if (evt.which == 16 && !control.active) {
            control.activate();
        }
    }).bind('boxselected', function(event) {
        var self = $(this);
        if (nav.active || self.data('deactivated')) {
            nav.deactivate();
            self.data('deactivated', false); // prevent CTRL keyup from re-activating
        }
    }).bind('boxdeselected', function(event) {
        if (!nav.active && !$(this).data('deactivated')) {
            nav.activate();
        }
    });
}

// parse GET variable string into an array
// from http://www.webdevelopmentcentral.net/2006/06/parsing-url-variables-with-javascript.html
function parse_GET(str) {
    // strip off the leading '?'
    str = str.substring(1);
    var vars = []
    var nvPairs = str.split("&");
    for (var i = 0; i < nvPairs.length; i++)
    {
        var nvPair = nvPairs[i].split("=");
        var obj = {name: nvPair[0],
                   value: nvPair[1]};
        vars.push(obj);
    }

    return vars;
}

function add_box(extent, selected) {
    map.box_control.setBox(extent, selected);
}

function clear_box(skip_bbox) {
    map.box_control.removeBox();
    if (!skip_bbox)
        $('#bbox').val(''); // set the form element
}

// remove the bounding box and deselect the area
function clear_area() {
    // deselect any selected areas
    var changed = $('select.area')
        .find(':selected[value!=""]')
        .parents('select')
        .val('')
        .change().length;

    // if no selection box was removed, try removing an user created
    // box instead.
    if (!changed) {
        clear_box();
        check_query();      // update the query results
    }
}

function zoom_to_area(id) {
    get_bbox(id, function(tbbox) {
        if (!tbbox)
            return false;

        map.zoomToExtent(OpenLayers.Bounds.fromArray(tbbox));
        return true;
    });
}

// Populate the area selection control
function populate_areas() {
    var select = $('select.area');

    // ensure the correct area selection is shown when changing area type
    var area_types = $('#area-type').change(function() {
        var id = $(this).val();
        select.removeAttr('name').hide();
        select.filter('#'+id).show().attr('name', 'a');
    });

    // ensure a bbox is created when an area is selected
    select.change(function() {
        var self = $(this);
        // deselect any other selected area selections
        select.not('#'+self.attr('id'))
            .find(':selected[value!=""]')
            .parents('select')
            .val('');

        var id = self.attr('value');
        if (!id) {
            clear_box();
            check_query();      // update the query results
        } else {
            get_bbox(id, function(tbbox) {
                if (!tbbox) {
                    clear_box();
                    return;
                } else {
                    var extent = new OpenLayers.Bounds(tbbox[0], tbbox[1], tbbox[2], tbbox[3]);
                    add_box(extent);
                    $('#bbox').val(extent.toBBOX()); // set the bounding box form value
                    map.zoomToExtent(extent);   // zoom to the box
                }

                check_query();      // update the query results
            });
        }
    });

    // if there's an existing area, select it
    if (area) {
        select.filter(':visible').change();
    } else if (bbox) {
        add_box(bbox);
        map.zoomToExtent(bbox);   // zoom to the box
    } else {
        // zoom to the UK as a default
        map.updateSize();
        zoom_to_area('GB');
    }

    // capture the drawbox and movebox events and act accordingly
    $(document).bind('drawbox movebox', function(event, bounds) {
        select.val('');         // unset any predefined area
        $('#bbox').val(bounds.toBBOX()); // set the form element
        check_query();          // update the query results
    });

    // ensure the map box and search criteria are updated when the
    // bounding box contents are changed
    $('#bbox').change(function() {
        var val = $(this).val();
        select.val('');         // unset any predefined area

        if (val) {
            // edit/create the box and zoom to it
            var extent = OpenLayers.Bounds.fromString(val);
            if (extent) {
                add_box(extent);
                map.zoomToExtent(extent);
            }
        } else {
            // remove the box
            clear_box(true);
        }

        check_query();          // update the query results
    });
}

// initialise the spatial search controls
function init_spatial_search() {
    // initialise the map
    init_map();

    // add the area selections
    populate_areas();

    // make the map full width
    $('#map').css('width', '100%');
    map.updateSize();
}

/* Initialise the search term controls.
 *
 * This provides the popup with the dropdowns and text boxes used to
 * compile searches for specific metadata fields.
 */
function init_search_term() {
    var caret = null;           // contains the position of the cursor caret
    var controls_active = false; // flags whether the controls are currently active

    // a wrapper for setting the status; can be extended for debugging
    var set_control_status = function(status) {
        controls_active = status;
    };

    // hide the search term controls
    var hide = function() {
        if (!controls_active)
            $('#search-term-controls').hide();
    };

    // update the query status
    var term_change = function() {
        if (!controls_active)
            check_query();
    };

    // ensure the query status is updated when the search term changes
    var search_term = $('#search-term').change(term_change);

    // activate a target control based on a substring match in the
    // current search term.
    var pattern = /(\w+)$/;
    function set_target(range_end) {
        var text = search_term.val().substr(0, range_end);
        var match = text.match(pattern);
        if (match) {
            var target = match[1];
            $('#target-type').val(target).change();
        }
    }

    search_term.keypress(
        // If a colon is typed activate the associated target control
        function(event) {
            switch (event.which) {
            case 58:                // colon (:)
                var range = search_term.caret();
                set_target(range.end);
                break;
            }
        }
    ).keydown(
        /* Capture backspace key strokes so we can set the appropriate
        target controls when a target is reached */
        function(event) {
            caret = search_term.caret();
            switch (event.which) {
            case 8:                 // backspace
                if (search_term.val().charAt(caret.end-2) == ':')
                    set_target(caret.end-2)
                break;
            }
        }
    ).focus(
        // Show the controls when the search term receives focus
        function() {
            $('#search-term-controls').show().alignWith(search_term, 'bltl');
        }
    ).blur(hide); // hide the controls when the search term looses focus

    // Flag the controls as being active
    var activate_controls = function() {
        set_control_status(true);
        caret = search_term.caret(); // store the caret position
    };

    // Flag the controls as not being active
    var deactivate_controls = function() {
        set_control_status(false);
        search_term.focus().caret(caret.end); // set the caret position based
    };

    // Flag the control status when the mouse moves over the control area
    $('#search-term-controls').hover(activate_controls, deactivate_controls);

    // Deal with the target control selector
    $('#target-type').focus(
        // take control of determining the search term control status
        function() {
            $('#search-term-controls').unbind('mouseenter mouseleave');
            set_control_status(true);
        }
    ).blur(
        // relinquish control of determining the search term control status
        function() {
            $('#search-term-controls').hover(activate_controls, deactivate_controls);
            deactivate_controls();
        }
    ).change(
        // When a target is choosen activate that target's control
        function() {
            var value = $(this).val();
            if (value) {
                var id = '#target-'+value;
                $('.target:not('+id+')').hide();
                $('#target-controls').show();
                $(id).val('').show();
                if (controls_active) {
                    $(id).focus();
                }
            } else {
                $('#target-controls').hide();
                deactivate_controls();
            }
        }
    );


    // Return activation control to the generic search term container
    $('#target-type option').click(function() {
        $('#search-term-controls').hover(activate_controls, deactivate_controls);
    });

    $('.target').focus(
        // Assume contol of the control status on focus
        function() {
            $('#search-term-controls').unbind('mouseenter mouseleave');
            set_control_status(true);
        }
    ).blur(
        // Relinquish control of the control status on blur
        function() {
            $('#search-term-controls').hover(activate_controls, deactivate_controls);
            deactivate_controls();
        }
    ).change(
        // Insert the choosen target value into the correct place in
        // the search term.
        function() {
            var self = $(this);
            var value = self.val();

            if (value) {
                var caret_start = caret.start;
                var caret_end = caret.end;
                var terms = search_term.val(); // current search terms

                // create the target string
                var target = self.attr('id').substr(7);
                var new_term = target+':'+value;
            
                // in case the cursor has been placed just before a colon,
                // move it after the colon.
                if (terms.charAt(caret_end) == ':')
                    caret_end += 1;

                // if the caret is not at the beginning we need to
                // check the preceding characters
                if (caret_end) {
                    char_check:
                    switch (terms.charAt(caret_end-1)) {
                    case ':':
                        // ensure the current target is replaced
                        var i = terms.substr(0, caret_end-1).lastIndexOf(' ');
                        if (i != -1)
                            caret_start = i+1;
                        else
                            caret_start = 0;
                        break;
                    case '-':
                        // ensure the exclusion character is respected
                        switch (terms.charAt(caret_end-2)) {
                        case '':
                        case ' ':
                            break char_check; // the outer switch
                        }
                    case ' ':
                        // a preceding space is fine
                        break;
                    default:
                        // we need to prefix the new term with a space
                        new_term = ' '+new_term;
                    }
                }

                // suffix with a space if adding the term in the middle of a string
                if (caret_end != terms.length && terms.charAt(caret_end) != ' ')
                    new_term += ' ';
            
                // Insert the new term at the caret then restore caret
                var prefix = terms.substr(0, caret_start) + new_term;
                terms = prefix + terms.substr(caret_end, terms.length);
                search_term.val(terms);
                caret.end = prefix.length;
                
                self.blur();
                term_change();  // ensure the query status is updated
            } else {
                self.blur();
            }
        }
    );
}

function init_date(id) {
    var input = $('#'+id);

    // a function to initialise the date picker
    var init_datepicker = function() {
        input.datepicker({
            onSelect: function(date, picker) {
                // trigger the change event, which is used by the
                // query checking code.
                input.change();
            },
            changeMonth: true,
            changeYear: true,
            yearRange: 'c-20:c+20',
            maxDate: '+0d'
        });
    }

    init_datepicker();
}

var query_check = 0;
function check_query() {
    query_check += 1;
    var check_count = query_check;

    var term = $('#criteria-term');
    var date = $('#criteria-date');
    var area = $('#criteria-area');

    // set the timeout for the image load
    function load() {
        term.empty();
        date.empty();
        area.empty();
        term.append('<span><img class="loading" src="/images/loading.gif" width="16" height="16" alt="[loading]"/> Updating search criteria...</span>');
    }
    var timeout = setTimeout(load, LOAD_DELAY);

    var url = script_root+'/full/query.json?'+$('#search-form').serialize();
    $.ajax({url: url,
            success: function(criteria) {
                clearTimeout(timeout);

                // only process if this is the latest check
                if (query_check != check_count)
                    return;

                var messages = $('#messages').empty();

                for (var i = 0; i < criteria['errors'].length; i++) {
                    messages.append('<p class="error">'+criteria['errors'][i]+'</p>');
                }

                term.empty();
                date.empty();
                area.empty();
                if (!criteria['terms'].length &&
                    !criteria['dates'].start && !criteria['dates'].end &&
                    !criteria['area'] && !criteria['bbox']) {
                    term.append('<span><strong>everything</strong> in the catalogue.</span>');
                    return;
                } else if (!criteria['terms'].length)
                    term.append('<strong>everything</strong>');
                else
                    term.append('<span>documents containing </span>');

                for (var i = 0; i < criteria['terms'].length; i++) {
                    var tterm = criteria['terms'][i];
                    if (tterm['op'])
                        term.append('<strong> '+tterm['op']+' </strong>');
                    term.append('<kbd>'+tterm['word']+'</kbd>');
                    if (tterm['target'][0] && tterm['target'][1])
                        term.append('<span> (in '+tterm['target'][1]+') </span>');
                    else if (tterm['target'][0] && !tterm['target'][1])
                        term.append('<span> (<span class="error">ignoring unknown target <strong>'+tterm['target'][0]+'</strong></span>) </span>');
                }

                if (criteria['dates'].start && criteria['dates'].end)
                    date.append('<span> between <strong>'+criteria['dates'].start+'</strong> and <strong>'+criteria['dates'].end+'</strong></span>');
                else if (criteria['dates'].start)
                    date.append('<span> since <strong>'+criteria['dates'].start+'</strong></span>');
                else if (criteria['dates'].end)
                    date.append('<span> before <strong>'+criteria['dates'].end+'</strong></span>');

                if (criteria['area'])
                    area.append('<span> in <strong>'+criteria['area']+'</strong></span>');
                else if (criteria['bbox']) {
                    var n = criteria['bbox'][3].toFixed(2);
                    var s = criteria['bbox'][1].toFixed(2);
                    var e = criteria['bbox'][2].toFixed(2);
                    var w = criteria['bbox'][0].toFixed(2);
                    area.append('<span> in <strong>'+n+'N '+s+'S '+e+'E '+w+'W</strong></span>');
                }
            },
            complete: function(req, status) {
                clearTimeout(timeout); // just to be sure!
            },
            dataType: 'json'});

    // if the query has changed we also need to update the result
    // details
    update_results();
}

var update_check = 0;
function update_results() {
    update_check += 1;
    var check_count = update_check;
    var block = $('#result-count');

    // set the timeout for the image load
    function load() {
        block.empty();
        block.append('<span><img class="loading" src="/images/loading.gif" width="16" height="16" alt="[loading]"/> Updating result count...</span>');
    }
    var timeout = setTimeout(load, LOAD_DELAY);

    var url = script_root+'/full.json?'+$('#search-form').serialize();
    $.ajax({url: url,
            success: function(results) {
                clearTimeout(timeout);

                // only process if this is the latest check
                if (update_check != check_count)
                    return;

                block.empty();
                block.append('<span><strong>'+results['hits']+'</strong> '+
                             ((results['hits'] != 1) ? 'results' : 'result')
                             +' returned in <strong>'+results['time'].toFixed(2)+'</strong> seconds.</span>');
            },
            error: function(req, status, e) {
                clearTimeout(timeout);

                // only process if this is the latest check
                if (update_check != check_count)
                    return;

                update_check += 1; // so the timeout wont fire
                var msg = null;
                if (req.readyState == 4 && req.status == 500) {
                    msg = 'The server failed to return the result count';
                } else {
                    msg = 'There is a problem obtaining the result count';
                }

                block.empty().append('<span class="error">'+msg+'.</span>');
            },
            complete: function(req, status) {
                clearTimeout(timeout); // just to be sure!
            },
            dataType: 'json'});
}

var _areas = {}                 // for caching bboxes
function get_bbox(id, callback) {
    if (!id) return false;

    // see if the bounding box is cached
    var bbox = _areas[id]
    if (typeof(bbox) != 'undefined') {
        callback(bbox);
        return true;
    }

    var url = script_root+'/spatial/areas/'+id+'/extent.json'
    $.ajax({url: url,
            success: function(bbox) {
                _areas[id] = bbox; // cache the bbox
                callback(bbox);
            },
            dataType: 'json'});

    return true;
}

/* Control for drawing bounding box

 This control manages the bounding box on the map. It is based on examples in:
 - http://dev.openlayers.org/docs/files/OpenLayers/Control-js.html
 - http://dev.openlayers.org/releases/OpenLayers-2.8/lib/OpenLayers/Control/SelectFeature.js

 The box should really be a customised class derived from
 OpenLayers.Marker.Box. This would clean the control code up and
 delegate appropriate functionality to the Box where it belongs. */
OpenLayers.Control.BoxDraw = OpenLayers.Class(OpenLayers.Control, {
    defaultHandlerOptions: {
        'single': true,
        'double': false,
        'pixelTolerance': 0,
        'stopSingle': false,
        'stopDouble': false
    },

    initialize: function(options) {
        this.handlerOptions = OpenLayers.Util.extend(
            {'keyMask': OpenLayers.Handler.MOD_CTRL},
            this.defaultHandlerOptions
        );

        OpenLayers.Control.prototype.initialize.apply(
            this, arguments
        );

        // this Handler.Box will intercept the shift-mousedown
        // before Control.MouseDefault gets to see it
        this.handler = new OpenLayers.Handler.DrawBox(
            this, {
                'done': this.drawBox
            },
            this.handlerOptions
        );

        // keep track of CTRL keydown position and prevent dragging
        // and resizing of an existing box if the CTRL key is pressed
        // down, as another box may be being drawn.
        this.keydown = false;
        var self = this;
        $(document).keydown(function(evt) {
            if (evt.which == 17) {
                self.keydown = true;
                if (self.box) {
                    var div = $(self.box.div);
                    if (div.data('selected')) {
                        div.resizable( "option", "disabled", true )
                            .draggable( "option", "disabled", true );

                        function enable_edit(event) {
                            if (event.which == 17) {
                                if (div.data('selected')) {
                                    div.resizable( "option", "disabled", false )
                                        .draggable( "option", "disabled", false );
                                }
                                $(document).unbind('keyup', enable_edit); // we only need to enable the edit once
                            }
                        }

                        // re-enable the editing once the key is released
                        $(document).bind('keyup', enable_edit);
                    }
                }
            }
        }).keyup(function(evt) {
            if (evt.which == 17)
                self.keydown = false;
        });
    },

    drawBox: function(position) {
        if (!(position instanceof OpenLayers.Bounds) || !this.active)
            return;

        var min = this.map.getLonLatFromPixel(
            new OpenLayers.Pixel(position.left, position.bottom)
        );
        var max = this.map.getLonLatFromPixel(
            new OpenLayers.Pixel(position.right, position.top)
        );
        var bounds = new OpenLayers.Bounds(
            min.lon, min.lat, max.lon, max.lat
        );

        this.setBox(bounds, true);

        jQuery(document).trigger('drawbox', [bounds]);
    },

    setBox: function(bounds, selected) {
        if (!this.active) return;

        // add the box to the map
        var box = new OpenLayers.Marker.Box(bounds);

        // add the drag and resize behaviour
        var div = jQuery(box.div);
        var ctrl = this;
        div.draggable({
            containment: '#map-holder',    // don't drag outside of the map
            cursor: 'crosshair',
            distance: 5,
            delay: 300,
            stop: function(event, ui) {
                // replace the existing box bounds with the new one
                var self = jQuery(this);
                var minx = ui.position.left;
                var maxy = ui.position.top;
                var maxx = minx + self.width();
                var miny = maxy + self.height();

                ctrl.moveBox(minx, miny, maxx, maxy);
            }
        })
        .resizable({
            handles: 'all',
            containment: '#map-holder',    // don't resize outside of the map
            distance: 5,
            delay: 300,
            stop: function(event, ui) {
                // replace the existing box bounds with the new one
                var minx = ui.position.left;
                var maxy = ui.position.top;
                var maxx = minx + ui.size.width;
                var miny = maxy + ui.size.height;

                ctrl.moveBox(minx, miny, maxx, maxy);
            }
        }).iclick({
            interval: 300,
            success: function(event) {
                if (jQuery(this).data('selected')) {
                    ctrl.deselectBox();
                } else {
                    ctrl.selectBox();
                }
            }
        });

        // add the custom handles for the resize
        div.find('.ui-resizable-ne').addClass('ui-custom-icon ui-icon-gripsmall-diagonal-ne');
        div.find('.ui-resizable-sw').addClass('ui-custom-icon ui-icon-gripsmall-diagonal-sw');
        div.find('.ui-resizable-nw').addClass('ui-custom-icon ui-icon-gripsmall-diagonal-nw');

        this.box_layer.addMarker(box); // add the box to the layer
        if (this.box)
            this.box_layer.removeMarker(this.box); // remove any previous box
        this.box = box;

        // define the initial state of the box
        if (selected) {
            this.selectBox();
        } else {
            this.deselectBox();
        }
    },

    selectBox: function() {
        if (!this.box || !this.active) return;

        var div = $(this.box.div);

        // only select if not already selected
        if (div.data('selected'))
            return;

        // set the box to be editable. If the CTRL key is depressed
        // then we need to make disable editing until it is released.
        if (this.keydown) {
            div.resizable( "option", "disabled", true )
                .draggable( "option", "disabled", true );

            function enable_edit(event) {
                if (event.which == 17) {
                    if (div.data('selected')) {
                        div.resizable( "option", "disabled", false )
                            .draggable( "option", "disabled", false );
                    }
                    $(document).unbind('keyup', enable_edit); // we only need to enable the edit once
                }
            }

            $(document).bind('keyup', enable_edit);
        } else {
            div.resizable( "option", "disabled", false )
                .draggable( "option", "disabled", false );
        }

        div.css(BOX_SELECTED)
            .data('selected', true);

        jQuery(document).trigger('boxselected', []);
    },

    deselectBox: function() {
        if (!this.box || !this.active) return;

        var div = $(this.box.div);
        var state = div.data('selected');

        // disable editing if not already disabled
        if (state !== false) {
            div.resizable( "option", "disabled", true )
                .draggable( "option", "disabled", true )
                .css(BOX_DESELECTED)
                .data('selected', false);
        }

        // trigger the event if switching selection state
        if (state === true)
            jQuery(document).trigger('boxdeselected', []);
    },

    removeBox: function() {
        if (this.box && this.active) {
            this.deselectBox(); // to restore app state
            this.box_layer.removeMarker(this.box);
            this.box = null;
        }
    },

    // move the box based on pixel locations
    moveBox: function (minx, miny, maxx, maxy) {
        if (!this.box || !this.active) return;

        var min = this.map.getLonLatFromPixel(new OpenLayers.Pixel(minx, miny));
        var max = this.map.getLonLatFromPixel(new OpenLayers.Pixel(maxx, maxy));
        this.box.bounds = new OpenLayers.Bounds(min.lon, min.lat, max.lon, max.lat);

        jQuery(document).trigger('movebox', [this.box.bounds]);
    },

    CLASS_NAME: "OpenLayers.Control.BoxDraw"
});


// The box chosen when the user draws a new area
OpenLayers.Handler.DrawBox = OpenLayers.Class(OpenLayers.Handler.Box, {

    // override the startBox so that it displays with the correct style
    startBox: function (xy) {
        OpenLayers.Handler.Box.prototype.startBox.apply(this, arguments);
        $(this.zoomBox).css(BOX_SELECTED);
    },

    CLASS_NAME: "OpenLayers.Handler.DrawBox"
});