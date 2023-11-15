/*
 *	SERVER interface - AJAX routines
 *  Usage: server_get_data(url, options)
 *	The url is the URL to request.
 *	Options can contain the following flags:
 *		- complete:		callback on completion (data  -can be null, options)
 *		- postdata:		data to send via POST
 *      - formdata:     create a formdata field before posting as POST
 *		- progress:		callback on operation progress (progress or -1 on failure, options)
 *		- nocache:		set to true if you want to specifically avoid these requests being cached.
 *      - onlineOnly:   only perform this request if currently online, do not retry.
 *	Francois Botman, 2012.
 *  Updated 2017, 2020.
 */

function Server() {
    var self = this;
    var serverCallbacks = {};
    var currentSessionRequests = {};

    self.db = new Dexie('pdfreview-server-sync');
    self.db.version(1).stores({todo: "++id,attempts"});

    self.syncInProgress = false;
    self.reauthenticationRequestInProgress = false;


    function _server_send(parameters, callbacks) {
        return new Promise(function(resolve) {
            if(!navigator.onLine) {
                if(callbacks.progress) callbacks.progress(-1);
                if(callbacks.complete) callbacks.complete({errorCode: -1, errorMsg: "Browser is offline."});
                return resolve({errorCode: -1, errorMsg: "Browser is offline."});
            }

            // The famous XMLHTTP object!!!
            function getHttpObj() {
                try {return new XMLHttpRequest();} catch (e) {}
                /* istanbul ignore next */
                {
                    try {return new ActiveXObject("Microsoft.XMLHTTP");} catch (e) {}
                    try {return new ActiveXObject("Msxml2.XMLHTTP");} catch(e) {}
                    return null;
                }
            }

            var http = getHttpObj();
            var send = parameters.url;
            if(parameters.nocache) {
                if(send.indexOf('?') >= 0) send += '&anticaching='+(new Date()).getTime();
                else send += '?anticaching='+(new Date()).getTime();
            }

            try {
                if(callbacks.progress) {
                    http.upload.onprogress = function(e) {
                        if(!e.lengthComputable) return;
                        var total = e.total || e.totalSize;
                        var current= e.loaded || e.position;
                        callbacks.progress(Math.round(current*50.0/total));
                    }
                    http.onprogress = function(e) {
                        if(!e.lengthComputable) return;
                        var total = e.total || e.totalSize;
                        var current= e.loaded || e.position;
                        callbacks.progress(Math.round(50 + current*50.0/total));
                    }
                }

                http.onerror = function(e, st) {
                    if(callbacks.progress) callbacks.progress(-1);
                    if(callbacks.complete) callbacks.complete({errorCode: -1, errorMsg: e});
                    resolve({errorCode: -1, errorMsg: e});
                }

                var postdata = parameters.postdata;
                if(!postdata && parameters.formdata) {
                    postdata = new FormData();
                    for(var i in parameters.formdata) {
                        var obj = parameters.formdata[i]
                        if(typeof obj === 'string') postdata.append(i, obj);
                        else postdata.append(i, JSON.stringify(obj));
                    }
                }
                http.open((postdata == null) ? 'GET' : 'POST', send, true);
                if(!postdata) http.setRequestHeader("Content-Type", "text/html");
                http.setRequestHeader("charset", "ISO-8859-1");

                http.onreadystatechange = function() {
                    if(http.readyState == 4) {
                        if(http.status == 200) {
                            var json;
                            try {
                                json = JSON.parse(http.responseText || "{}");
                            } catch(e) {
                                json = {errorCode: 10000, errorMsg: "Failed to parse server-issued JSON: " + http.responseText};
                            }
                            if(callbacks.progress) callbacks.progress(100);
                            if(callbacks.complete) callbacks.complete(json);
                            $('#offline-status-text').hide();
                            resolve(json);
                        }
                        else {
                            $('#offline-status-text').show().html('Experiencing difficulties (<A HREF="?reauthentication-attempt=' + (new Date()).getTime() + '&review=' + window.reviewId + '">are you logged out</A>?)');
                            console.error("Failed to fetch request", http);
                            if(callbacks.progress) callbacks.progress(-1);
                            if(callbacks.complete) callbacks.complete({errorCode: -1, errorMsg: "Did not return HTTP 200."});
                            resolve({errorCode: -1, errorMsg: "Did not return HTTP 200."});
                        }
                    }
                }
                http.send(postdata ? postdata : null);
            } catch(e) {
                if(callbacks.progress) callbacks.progress(-1);
                if(callbacks.complete) callbacks.complete({errorCode: -1, errorMsg: e});
                resolve({errorCode: -1, errorMsg: e});
            }
        });
    }

    function server_sync() {
        if(!navigator.onLine || self.syncInProgress) return;

        var cnt = 0;
        self.syncInProgress = true;
        // Limit to those with low attempt numbers.
        // Limit to one simultaneous connection, otherwise sequential updates may get out of order.
        self.db.todo.where("attempts").below(20).first(function(obj) {
            cnt++;
            if(!currentSessionRequests[obj.id]) offlineCacheStatus("uploading");
            return new Promise(function(resolve) {
                _server_send(obj, serverCallbacks[obj.id] || {}).then(function(json) {
                    if(obj.onlineOnly || (json && json.errorCode >= 0)) {
                        // Success! (or given up trying)
                        delete serverCallbacks[obj.id];
                        self.db.todo["delete"](obj.id).then(resolve);
                    }
                    else {
                        // Failure -- schedule for later.
                        self.db.todo.update(obj.id, {attempts: obj.attempts + 1}).then(resolve);
                    }
                });
            });
        }).then(function() {
            self.syncInProgress = false;
            if(cnt) setTimeout(function() {server_sync();}, 1);
        })["catch"](function() {
            self.syncInProgress = false;
            setTimeout(function() {server_sync();}, 5000);  // Retry later?
        });
    }

    function server_get_data(url, options) {

        var parameters = {url:        url,
                          postdata:   options.postdata,
                          formdata:   options.formdata,
                          nocache:    options.nocache,
                          onlineOnly: options.onlineOnly,
                          attempts:   0
                        };
        var callbacks = {progress: options.progress, complete: options.complete};

        if(!navigator.onLine && options.onlineOnly) {
            if(callbacks.progress) callbacks.progress(-1);
            if(callbacks.complete) callbacks.complete({errorCode: -1, errorMsg: "Browser is offline."});
            return;
        }

        // Postdata cannot be postponed
        if(options.postdata) {
            return _server_send(parameters, callbacks);
        }

        // Otherwise route this request through the offline cache for resilience.
        return self.db.todo.put(parameters).then(function(id) {
            currentSessionRequests[id] = true;
            serverCallbacks[id] = callbacks;
            return server_sync();
        });
    }
    self.server_get_data = server_get_data;



    function changeOnlineState(state) {
        if(state == "online")  document.body.className = "online";
        if(state == "offline") document.body.className = "offline";
        server_sync();
    }

    window.addEventListener("online",  function() {changeOnlineState("online");});
    window.addEventListener("offline", function() {changeOnlineState("offline");});
    document.addEventListener("online",  function() {changeOnlineState("online");});
    document.addEventListener("offline", function() {changeOnlineState("offline");});
    document.body.addEventListener("online",  function() {changeOnlineState("online");});
    document.body.addEventListener("offline", function() {changeOnlineState("offline");});
    changeOnlineState(navigator.onLine ? "online" : "offline");

    function offlineCacheStatus(status) {
        var notificationDelay = 10000;
        function hideOfflineNotification() {
            $('#offline-status-text').hide();
        }

        if(self.statusTimeout) clearTimeout(self.statusTimeout);

        if(status == "downloading") {
            $('#offline-status-text').show().html("Downloading files for offline use.");
            self.statusTimeout = setTimeout(function() {offlineCacheStatus("ready");}, 2000);
        }
        else if(status == "uploading") {
            $('#offline-status-text').show().html("Uploading data from offline sessions.");
            self.statusTimeout = setTimeout(function() {offlineCacheStatus("ready-synced");}, 2000);
        }
        else if(status == "error") {
            $('#offline-status-text').show().html("<B>Not</B> available offline.");
        }
        else if(status == "ready") {
            $('#offline-status-text').show().html("Ready for offline use.");
            self.statusTimeout = setTimeout(hideOfflineNotification, notificationDelay);
        }
        else if(status == "ready-synced") {
            $('#offline-status-text').show().html("Offline data uploaded.");
            self.statusTimeout = setTimeout(hideOfflineNotification, notificationDelay);
        }
        else hideOfflineNotification();
    }
    $('#offline-status-text').hide();

    // If this browser/server supports a ServiceWorker, use that instead.
    // Service workers only work on HTTPS, so don't even try if that's not what we're using.
    if('serviceWorker' in navigator && location.protocol.match("https") ) {
     try {
         offlineCacheStatus("downloading");
         navigator.serviceWorker.register(window.scriptURL + '?manifest=serviceworker', {scope: './'}).then(function(registration) {
             if(window.console) console.info("Using ServiceWorkers to provide offline access.");
             if(registration) {
                 offlineCacheStatus("ready");
                 registration.update();
             }
             else offlineCacheStatus("error");
         });
     } catch(error) {
         if(window.console) console.info("Service workers failed to register, hopefully the application cache still works.");
         offlineCacheStatus("error");
     }
    }

    function _force_server_sync(info) {
        if(!info) console.log("Forcing server sync");
        if(!info && !navigator.onLine) console.log("Cannot perform sync as the navigator is offline", navigator.onLine);
        if(!info) self.db.todo.toArray().then(function(data) {
            console.log("[debug] Captured offline db items to synchronise:", data);
        });
        // Maintenance operations on the offline server todo list:
        self.syncInProgress = false;
        self.db.todo.where("attempts").aboveOrEqual(20).each(function(obj) {
            obj.attempts = 0;   // reset # attempts
            self.db.todo.update(obj.id, obj);
        });
        server_sync();
    }
    window.force_server_sync = _force_server_sync;
    _force_server_sync(true);
}

Server.prototype.get_data = function(url, options) {
    var self = this;
    return self.server_get_data(url, options);
}
