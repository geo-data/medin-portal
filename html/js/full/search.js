// how long before loading messages should be displayed in milliseconds
var LOAD_DELAY = 1000;

// jQuery CSS map determining the style of the area box
var BOX_SELECTED = {
    'border-color': '#0B8AB3',
    'opacity': '1',
    'background-image': "url('/images/area-fill-selected.png')",
    'background-repeat': 'repeat'
};

var BOX_DESELECTED = {
    'border-color': '#CA0000',
    'opacity': '1',
    'background-image': "url('/images/area-fill.png')",
    'background-repeat': 'repeat'
};

function stop_box_edit(event) {
    if (!box)
        return;

    $(box.div).data('edit', false);
}

function add_box(extent) {
    // add the box to the map
    var newbox = new OpenLayers.Marker.Box(extent);

    // move the box based on pixel locations
    function move_box(minx, miny, maxx, maxy) {
        var min = map.getLonLatFromPixel(new OpenLayers.Pixel(minx, miny));
        var max = map.getLonLatFromPixel(new OpenLayers.Pixel(maxx, maxy));
        newbox.bounds = new OpenLayers.Bounds(min.lon, min.lat, max.lon, max.lat);

        $('#area').val('');                     // unset any predefined area
        $('#bbox').val(newbox.bounds.toBBOX()); // set the form element
        check_query();                          // update the query results
    }

    // add the drag and resize behaviour
    var div = $(newbox.div);
    div.css(BOX_DESELECTED)
    .draggable({
        containment: '#map',    // don't drag outside of the map
        disabled: true,
        cursor: 'crosshair',
        start: function(event, ui) {
            $(this).data('edit', false); // prevent box being deselected on stop
        },
        stop: function(event, ui) {
            // replace the existing box bounds with the new one
            var self = $(this);
            var minx = ui.position.left;
            var maxy = ui.position.top;
            var maxx = minx + self.width();
            var miny = maxy + self.height();

            move_box(minx, miny, maxx, maxy);
        }
    })
    .resizable({
        handles: 'all',
        containment: '#map',    // don't resize outside of the map
        distance: 5,
        start: function(event, ui) {
            $(this).data('edit', false); // prevent box being deselected on stop
        },
        stop: function(event, ui) {
            // replace the existing box bounds with the new one
            var minx = ui.position.left;
            var maxy = ui.position.top;
            var maxx = minx + ui.size.width;
            var miny = maxy + ui.size.height;

            move_box(minx, miny, maxx, maxy);
        }
    }).mousedown(function() {
        $(this).data('edit', true);
    }).mouseup(function () {
        var self = $(this);
        // Should we check the resizing?
        if (!self.data('edit'))
            return;

        if (self.resizable( "option", "disabled" )) {
            // deactivate all navigation controls
            var controls = map.getControlsByClass('OpenLayers.Control.Navigation');
            for (var i = 0; i < controls.length; i++) {
                controls[i].deactivate()
            }

            // set the box to be resizable
            self.resizable( "option", "disabled", false )
                .draggable( "option", "disabled", false );
            self.css(BOX_SELECTED);
        } else {
            // reactivate all navigation controls
            var controls = map.getControlsByClass('OpenLayers.Control.Navigation');
            for (var i = 0; i < controls.length; i++) {
                controls[i].activate()
            }

            // disable resizing
            self.resizable( "option", "disabled", true )
                .draggable( "option", "disabled", true );
            self.css(BOX_DESELECTED);
        }
    })
    .resizable( "option", "disabled", true );

    // add the custom handles for the resize
    div.find('.ui-resizable-ne').addClass('ui-custom-icon ui-icon-gripsmall-diagonal-ne');
    div.find('.ui-resizable-sw').addClass('ui-custom-icon ui-icon-gripsmall-diagonal-sw');
    div.find('.ui-resizable-nw').addClass('ui-custom-icon ui-icon-gripsmall-diagonal-nw');

    boxes.addMarker(newbox);
    
    clear_box();                // remove any previous box

    bbox = extent;
    box = newbox;
    
    map.zoomToExtent(extent);   // zoom to the box

    $('#bbox').val(extent.toBBOX()); // set the form element
}

// remove the bounding box and deselect the area
function clear_area() {
    var select = $('#area')
    select.val('');
    select.change();
}

function clear_box() {
    if (box) {
        boxes.removeMarker(box);
        box = null;
    }

    $('#bbox').val('');
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
    var select = $('#area');

    // ensure a bbox is created when an area is selected
    select.change(function() {
        var id = $(this).attr('value');
        if (!id) {
            clear_box();
            return;
        }
        
        get_bbox(id, function(tbbox) {
            if (!tbbox) {
                clear_box();
                return;
            }

            var extent = new OpenLayers.Bounds(tbbox[0], tbbox[1], tbbox[2], tbbox[3]);
            add_box(extent);
        });
    });

    // if there's an existing area, select it
    if (area) {
        select.val(area);
        select.change();
    } else if (bbox) {
        add_box(bbox);
    } else {
        // zoom to the UK as a default

        // The map is hidden to begin with and needs to be initialised
        // when it is first shown
        $('body').bind('fieldsetview', function(event, id) {
            if (id != 'spatial-search')
                return;
            
            map.updateSize();
            zoom_to_area('GB');
            $(this).unbind(event); // we don't need this event any more
        });
    }
}

function init_date(id) {
    var input = $('#'+id);
    var text = $('#'+id+'-text');

    // a function to initialise the date picker
    var init_datepicker = function() {
        input.datepicker({
            onClose: function(new_date, picker) {
                if (!new_date) {
                    input.hide();
                    text.show();
                }
            },
            onSelect: function(date, picker) {
                // trigger the change event, which is used by the
                // query checking code.
                input.change();
            }
        });
    }

    var has_date = input.val();
    // initialise the date picker if a date is present
    if (has_date) {
        init_datepicker();
        text.hide();
        input.show();
    }

    text.one('click', function() {
        $(this).hide();
        input.show();

        // initialise the date picker if there was no initial date
        if (!has_date) {
            init_datepicker();
        }
        
        input.datepicker('show');
        
        // for subsequent clicks
        text.click(function() {
            $(this).hide();
            input.show();
            input.datepicker('show');
        });
    });
}

function toggle(id, show_txt, hide_txt) {
    var ele = $('#'+id);
    if (ele.is(':visible')) {
        $('#'+id+'-link').text(show_txt);
        ele.hide('fast');
    } else {
        $('#'+id+'-link').text(hide_txt);
        ele.show('fast');
    }
}

function toggle_fieldset(id) {
    var fieldset = $('#'+id);

    if (fieldset.hasClass('off')) {
        fieldset.removeClass('off');
        fieldset.children('div').show('fast', function() {
            $('body').trigger('fieldsetview', [id]);
        });
    } else {
        fieldset.children('div').hide('fast', function() {
            fieldset.addClass('off');
        });
    }
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
                else if (criteria['bbox'])
                    area.append('<span> in <strong>your specified area</strong></span>');
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
