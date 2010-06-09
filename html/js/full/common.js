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
        fieldset.children('div.content').show('fast', function() {
            $(document).trigger('fieldsetview', [id]);
        });
    } else {
        fieldset.children('div.content').hide('fast', function() {
            fieldset.addClass('off');
        });
    }
}

// Initialise the page once loaded
$(function() {
	// let the comment field be resized
	$(document).bind('fieldsetview', function(event, id) {
        if (id != 'comment')
            return;

		$('#comment-form textarea').resizable({handles:'se'})
        $(this).unbind(event); // we don't need this event any more
    });
});