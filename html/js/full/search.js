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
    var url = script_root+'/full/query.json?'+$('#search-form').serialize();
    $.ajax({url: url,
            success: function(criteria) {
                // only process if this is the latest check
                if (query_check != check_count)
                    return;
                
                var messages = $('#messages').empty();
                for (var i = 0; i < criteria['errors'].length; i++) {
                    messages.append('<p class="error">'+criteria['errors'][i]+'</p>');
                }

                var term = $('#criteria-term').empty();
                var date = $('#criteria-date').empty();
                var area = $('#criteria-area').empty();

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
                    area.append('<span> which are in <strong>'+criteria['area']+'</strong></span>');
                else if (criteria['bbox'])
                    area.append('<span>which are in <strong>your specified area</strong></span>');
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
