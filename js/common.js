/*
 * Javascript functions common for all screens.
 * Francois Botman, 2017.
 */

function cancel(e) {
    e.preventDefault();
    e.stopPropagation();
    return false;
}

$.urlParam = function(name){
    var results = new RegExp('[\?&]' + name + '=([^&#]*)').exec(window.location.href);
    if (results == null) return null;
    return results[1] || 0;
}

if(!Array.prototype.indexOf && !Array.indexOf) {
    Array.prototype.indexOf = function(item) {
        var i = this.length;
        while (i--) if (this[i] === item) return i;
        return -1;
    }
}


function api(url) {
    var self = $("table");
    if(!navigator.onLine) return alert("This action cannot be performed offline -- please try again when you are online.");
    self.addClass("loading-animation");
    server.get_data(url, { nocache: true, onlineOnly: true, complete: function(p) {
        self.removeClass("loading-animation");
        if(p && p.errorCode == 0) {
            // Successfully completed. Now let's do something about it.
            if(p.url) window.open(p.url);
            else window.location.reload();
        }
        else if(p && p.errorCode == 3 && !url.match("password=")) {
            var password = prompt("Failed to render archive PDF.\nOne possible reason might be that the PDF is password protected. If so, please enter the file password below.")
            api(url + "&password=" + password)
        }
        else {
            alert("Failed to comply." + (p ? "\n"+p.errorMsg : ""));
        }
    }});
}

window.addEventListener('unhandledrejection', function(error) {
    // Dexie has a tendency to quitely blow up. But we want this to be caught by our main error handler.
    let reason = event.reason;
    console.error("unhandledrejectionerror", error, reason, reason.stack);
    throw new Error("Unhandled database error: " + error + ": " + reason + ": " + reason.stack);
});
