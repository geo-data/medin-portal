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

		$('#comment-form textarea').resizable({handles:'se'});
        $(this).unbind(event); // we don't need this event any more
    });
});