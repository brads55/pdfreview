/*
 * Javascript functions to handle modal tool windows.
 * Francois Botman, 2017.
 */

function ModalTool(id, object, onaction) {
    var self = this;
    this.id      = id;
    this.dialog  = $('#' + id);
    var offset   = $(object).offset();
    var left     = offset.left + $(object).width()/2 - 10;
    var top      = offset.top  + $(object).height()  + 14;

    // Show dialog
    function position_element() {
        var offset = $(object).offset();
        var left   = offset.left + $(object).width()/2 - 10;
        var top    = offset.top  + $(object).height()  + 14;
        self.dialog.css({left: left, top: top});
    }
    this.dialog.show();
    position_element();

    // Handle UI events
    $('#' + id + ' .autofocus').focus();
    $('#' + id + ' .tool-enter-action').val("").on("keypress", function (e) {
        if (e.which == 13 && !e.ctrlKey && !e.shiftKey && !e.altKey && !e.metaKey) {        // ENTER
            if(onaction) onaction(e.target);
            return cancel(e);
    }});
    $('#' + id + ' .tool-change-action').on("change", function(e) {
        if(onaction) onaction(e.target);
    });
    $('#' + id + ' .tool-close-action').on("click", function(e) {
        if(onaction) onaction(e.target);
        self.close();
    });
    $(window).on("resize.tool", position_element)
    self.reposition = position_element;
}

ModalTool.prototype.focus = function() {
    $('#' + this.id + ' .autofocus').focus();
}
ModalTool.prototype.select = function() {
    $('#' + this.id + ' .autofocus').focus().select();
}

ModalTool.prototype.close = function() {
    this.dialog.hide();
    $('#' + this.id + " .tool-enter-action").off("keypress");
    $('#' + this.id + ' .tool-change-action').off("change");
    $(window).off("resize.tool");
}
