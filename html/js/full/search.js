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
function init_search_map() {
    var nav = init_map();                 // the base map initialisation

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
    } else if (bboxes) {
        var bbox = new OpenLayers.Bounds();
        for (var i = 0; i < bboxes.length; i++) {
            bbox.extend(bboxes[i]);
        }
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
    init_search_map();

    // add the area selections
    populate_areas();

    // make the map full width
    $('#map').css('width', '100%');
    map.updateSize();

    // create the layer switcher control
    $('#layer-control').olLayerControl(map);

    // set up the button for toggling the layer control visibility
    $('#toggle-layer-control').click(function onClick() {
        if ($('#layer-control').is(":visible")) {
            $('#layer-control').fadeOut('fast');
        } else {
            $('#layer-control').fadeIn('fast');
        }
    });
}

/* Initialise the search term controls.
 */
function init_search_term() {
    init_theme_dropdown($('#data-themes'), 'sub-themes');
    init_theme_dropdown($('#sub-themes'), 'parameters');
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

    var data_themes = $('#data-themes select:first');
    var sub_themes = $('#sub-themes select:first');
    var parameters = $('#parameters select:first');

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
                    !criteria['area'] && !criteria['bbox'].length &&
                    !criteria['data_themes'].length &&
                    !criteria['sub_themes'].length &&
                    !criteria['parameters'].length &&
                    !criteria['data_holders'].length &&
                    !criteria['access_types'].length) {
                    term.append('<span><strong>everything</strong> in the catalogue.</span>');
                    return;
                } else if (!criteria['terms'].length &&
                           !criteria['data_themes'].length &&
                           !criteria['sub_themes'].length &&
                           !criteria['parameters'].length &&
                           !criteria['data_holders'].length &&
                           !criteria['access_types'].length)
                    term.append('<strong>everything</strong>');
                else
                    term.append('<span>documents ' + (criteria['terms'].length ? ' containing' : '') + '</span>');

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

                var theme_labels = {
                    data_themes: 'with any parameters matching the data theme',
                    sub_themes: 'with any parameters matching the sub theme',
                    parameters: 'with the parameter'
                },
                    theme_key = null;

                if (criteria['parameters'].length) {
                    theme_key = 'parameters';
                } else if (criteria['sub_themes'].length) {
                    theme_key = 'sub_themes';
                } else if (criteria['data_themes'].length) {
                    theme_key = 'data_themes';
                }
                if (theme_key) {
                    var label = '<span> ' + theme_labels[theme_key];
                    if (criteria[theme_key].length > 1) label += 's';
                    label += '</span>';
                    term.append(label);

                    var themes = [];
                    for (i = 0; i < criteria[theme_key].length; i++) {
                        themes.push('<kbd>' + criteria[theme_key][i][1] + '</kbd>');
                    }
                    term.append('<span> ' + themes.join(' or ') + ' </span>');
                }

                if (criteria['data_holders'].length) {
                    var holders = [];
                    for (i = 0; i < criteria['data_holders'].length; i++) {
                        holders.push('<kbd>' + criteria['data_holders'][i][1] + '</kbd>');
                    }
                    term.append('<span> ' + ((theme_key) ? ' and' : '') + ' held by ' + holders.join(' or ') + ' </span>');
                }

                if (criteria['access_types'].length) {
                    var types = [];
                    for (i = 0; i < criteria['access_types'].length; i++) {
                        types.push('<kbd>' + criteria['access_types'][i][1] + '</kbd>');
                    }
                    term.append('<span> having the access type ' + types.join(' or ') + ' </span>');
                }

                if (criteria['dates'].start && criteria['dates'].end)
                    date.append('<span> between <strong>'+criteria['dates'].start+'</strong> and <strong>'+criteria['dates'].end+'</strong></span>');
                else if (criteria['dates'].start)
                    date.append('<span> since <strong>'+criteria['dates'].start+'</strong></span>');
                else if (criteria['dates'].end)
                    date.append('<span> before <strong>'+criteria['dates'].end+'</strong></span>');

                if (criteria['area'])
                    area.append('<span> in <strong>'+criteria['area']+'</strong></span>');
                else if (criteria['bbox'].length) {
                    function formatNorthing(northing) {
                        return northing + ((northing >= 0) ? 'N' : 'S');
                    }
                    for (var i = 0; i < criteria['bbox'].length; i++) {
                        var n = formatNorthing(criteria['bbox'][i][3].toFixed(2));
                        var s = formatNorthing(criteria['bbox'][i][1].toFixed(2));
                        var e = criteria['bbox'][i][2].toFixed(2);
                        var w = criteria['bbox'][i][0].toFixed(2);
                        area.append('<span> in <strong>'+n+' '+s+' '+e+'E '+w+'W</strong></span>');
                    }
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

var _areas = {};                 // for caching bboxes
function get_bbox(id, callback) {
    if (!id) return false;

    // see if the bounding box is cached
    var bbox = _areas[id];
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

var do_check_query = true;
function init_theme_dropdown(dropdown, id) {
    dropdown.change(function onSelect(event) {
        var value = $(this).find('option:selected').val(),
            url = 'full/vocabs/' + id + '/' + value;

        if (do_check_query) check_query();
        
        // set the child with a default value
        $('#'+ id + ' select:first').val('_all')
            .change(); // and trigger a change to propagate to any sub dropdowns

        if (value == '_all') {
            $('#'+ id).hide();  // we don't want to see the child
            return;
        }

        $('#'+ id + ' div.box-loading').show();         //show the loading div
        $('#'+ id + ' > div:not(.box-loading)').hide(); //hide all other divs
        $('#'+ id).show();
        
        $.getJSON(url, function onSuccess(data) {
            var items = ['<option value="_all">All</option>'];
            
            data.forEach(function onItem(item) {
                items.push('<option value="' + item[0] + '">' + item[1] + '</option>');
            });

            do_check_query = false; // don't run a query check due to this change
            if (items.length > 1) {
                $('#'+ id + ' select:first').empty().append(items.join('')) //add the options to the select
                    .change();                                              //trigger a change
                $('#'+ id + ' div.box-on').show();         //show the on div
                $('#'+ id + ' > div:not(.box-on)').hide(); //hide all other divs
            } else {
                $('#'+ id + ' select:first').change();      //trigger a change
                $('#'+ id + ' div.box-off').show();         //show the off div
                $('#'+ id + ' > div:not(.box-off)').hide(); //hide all other divs
            }
            do_check_query = true; //query checks can be run again
        });
    });
}
