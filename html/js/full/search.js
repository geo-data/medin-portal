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
