/*
 * Javascript functions to handle modal dialogs.
 * Francois Botman, 2017.
 */

function ModalDialog(id, onclose) {
    this.id      = id;
    this.dialog  = $('#' + id);
    this.overlay = $('#modal-container');
    this.onclose = onclose;
    
    this.open();
}

ModalDialog.prototype.open = function() {
    var self  = this;

    if(window.modalShown) {
        // A dialog is currently visible -- stall
        return setTimeout(function() {
            self.open.call(self);
        }, 1000);
    }
    window.modalShown = true;
    self.overlay.show();
    self.dialog.show();
    var close = function() {self.close.call(self, this);};

    // Register event handlers
    $('#' + self.id + " .button.modal-close").on("click", close);
    this.overlay.on("click", close);
    this.dialog.on ("click", function(e) { e.stopPropagation();});
    $(document).on("keydown.modal", function(e) {
        if (e.which == 27) close(); // ESCAPE
    });

    $('#' + self.id + " .modal-enter-close").on("keypress", function (e) {
        if ((e.which == 10 || e.which == 13) && (e.ctrlKey || e.shiftKey || e.altKey || e.metaKey)) {        // ENTER
            close.call(e.target);
            return cancel(e);
    }});
    $('#' + self.id + ' .autofocus').focus();
    $('#' + self.id + ' .clear').val("");
}

ModalDialog.prototype.close = function(parameters) {
    window.modalShown = false;
    $('#' + this.id + " .button.modal-close").off("click");
    this.overlay.off("click");
    $(document).off("keydown.modal");
    $('#' + this.id + " .modal-enter-close").off("keypress");
    this.dialog.hide();
    this.overlay.hide();
    if(this.onclose) this.onclose(this.dialog, parameters);
}
