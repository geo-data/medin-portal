/* The iClick jQuery plugin

An iclick is similar to the jquery click event except that a click is
defined as occurring within a specific interval between mousedown and
mouseup events (default 300ms).

On mousedown, an optional 'start' callback is run. If mouseup is
triggered within the interval, the optional success callback is run,
otherwise the optional 'failure' callback is run.

see http://docs.jquery.com/Plugins/Authoring for details on jQuery
plugins */
(function($) {
    $.fn.iclick = function(settings) {

        var config = {'interval': 300,
                      'start': null,
                      'success': null,
                      'failure': null};

        if (typeof(settings) == 'object')
            $.extend(config, settings);

        return this.each(function() {
            var self = $(this);
            var ctxt = this;    // the DOM element
            self.mousedown(function(event) {
                var timeout = null;

                function success(event) {
                    clearTimeout(timeout);
                    self.unbind('mouseup', success);

                    if (typeof(config.success) == 'function')
                        config.success.apply(ctxt, [event]);
                }

                function failure() {
                    self.unbind('mouseup', success);

                    if (typeof(config.failure) == 'function')
                        config.failure.call(ctxt);
                }

                self.mouseup(success);
                timeout = setTimeout(failure, config.interval);

                if (typeof(config.start) == 'function')
                    config.start.apply(ctxt, [event]);
            });
        });
    }
})(jQuery);
