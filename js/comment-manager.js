/*
 * Javascript functions to help with review comments.
 * Francois Botman, 2017.
 */


function CommentManager(pdfApp, commentContainer) {
    var self = this;
    self.pdfApp           = pdfApp;
    self.commentContainer = commentContainer;
    self.filterButton     = $('#button-comment-filter');
    self.statusList       = ["None", "Accepted", "Rejected", "Cancelled", "In Progress", "Completed"];
    self.reviewerList     = [];
    self.rstfilters       = {txt:           "",
                             unreadOnly:    false,
                             status:        [],
                             reviewers:     []};
    self.commentDB        = new Dexie('pdfreview-comment-list-for-review-' + window.reviewId);
    self.commentDB.version(1).stores({comments: "id,pageId"});

    self.filters          = jQuery.extend({}, self.rstfilters,
                                JSON.parse(window.localStorage["filters_" + window.reviewId] || '{}'));

    self.goToComment      = location.hash && location.hash.match("page|comment");

    // Create comment-per-page containers
    for(var i = 0; i < self.pdfApp.pdf.numPages; i++) {
        var div = document.createElement("div");
        div.id = "review-comments-for-page-" + i;
        self.commentContainer.appendChild(div);
    }
    var div = document.createElement("div");
    div.id = "review-comments-for-deletions";
    self.commentContainer.appendChild(div);

    // Get list of comments
    self.refreshComments(true);
    self.applyFilters();
    self.fetchAllComments();
    window.addEventListener("online", function() {self.fetchAllComments();});
    document.addEventListener("online", function() {self.fetchAllComments();});
    document.body.addEventListener("online", function() {self.fetchAllComments();});
    setInterval(function() {self.fetchAllComments();}, 1 * 60 * 1000);  // Refresh comments every 1 minutes


    // Enable filtering UI
    function openFilter(e) {
        // Prepare UI to match current filters
        $('#comment-filter-text').val(self.filters.txt);
        $('#comment-filter-unread').prop("checked", self.filters.unreadOnly);
        var stats = $('#comment-placeholder-status').empty();
        var revs  = $('#comment-placeholder-reviewers').empty();
        for(var i = 0; i < self.statusList.length; i++) {
            stats.append($('<INPUT>').prop({type: "checkbox", id: "comment-status-box-"+i, checked: (self.filters.status.indexOf(self.statusList[i]) < 0)}))
                 .append($('<LABEL>').prop({'for': "comment-status-box-"+i}).text(self.statusList[i]));
        }
        for(var i = 0; i < self.reviewerList.length; i++) {
            revs.append($('<INPUT>').prop({type: "checkbox", id: "comment-reviewers-box-"+i, checked: (self.filters.reviewers.indexOf(self.reviewerList[i]) < 0)}))
                .append($('<LABEL>').prop({'for': "comment-reviewers-box-"+i}).text(self.reviewerList[i]));
        }

        new ModalDialog("dialog-comment-filters", function(dialog, button) {
            if($(button).data("button") == "submit") {
                self.filters.txt        = $('#comment-filter-text').val();
                self.filters.unreadOnly = $('#comment-filter-unread').prop("checked");
                self.filters.status = [];
                self.filters.reviewers = [];
                for(var i = 0; i < self.statusList.length; i++) {
                    if(!$("#comment-status-box-"+i).prop("checked")) self.filters.status.push(self.statusList[i]);
                }
                for(var i = 0; i < self.reviewerList.length; i++) {
                    if(!$("#comment-reviewers-box-"+i).prop("checked")) self.filters.reviewers.push(self.reviewerList[i]);
                }
                self.flashing = null;
                self.applyFilters();
            }
            else if($(button).data("button") == "clear") {
                self.filters = jQuery.extend({}, self.rstfilters);
                self.filterButton.removeClass("active");
                self.applyFilters();
            }

            window.localStorage["filters_" + window.reviewId] = JSON.stringify(self.filters);
        });
    }

    self.filterButton.on("click", openFilter);
    $(window).on("keydown.mousetools", function(e) {
        if(e.which == 72 && (e.ctrlKey || e.metaKey)) {     // CTRL+H
            openFilter(e);
            return cancel(e);
        }
    });

    // Prepare palette
    $(window).on("contextmenu", function(e) {
        if(self.paletteActive) return cancel(e);
    });
    $(window).on("mouseup", function(e) {
        if(self.paletteActive) {
            var status = $(e.target).data("status");
            $('#status-palette').hide().css({left: 0, top: 0});
            if(status) {
                // Only set status for the top-level comment
                var commentId = self.paletteActive;
                var div = document.getElementById("review-comment-" + commentId);
                while(div && div.replyToId) {
                    commentId = div.replyToId;
                    div = document.getElementById("review-comment-" + commentId);
                }
                self.commentDB.comments.get(commentId).then(function(comment) {
                    if(comment.status != status) {
                        comment.status = status;
                        comment.unsync = true;
                        self.addComment(comment, "update-comment-status");
                    }
                });
            }
            self.paletteActive = false;
            return cancel(e);
        }
    });
    self.onCommentContext = function(e) {
        if(e.which == 3) {
            self.paletteActive = e.data.commentid;
            self.selectComment(e.data.commentid, false);
            $('#status-palette').show().css({left: e.pageX - 100, top: e.pageY - 100});
            return cancel(e);
        }
    };

    window.stressTest = function(num) {
        if(num > 500) return console.error("That's too stressful for a stress test :/ (try 100).");
        for(var i = 0; i < num; i++) {
            var x = Math.floor(Math.random() * 500);
            var y = Math.floor(Math.random() * 800);
            var w = Math.floor(Math.random() * 200);
            var h = Math.floor(Math.random() * 300);
            self.addComment({pageId: Math.floor(Math.random() * self.pdfApp.pdf.numPages),
                             type:   "highlight",
                             unsync: true,
                             owner:  true,
                             msg:    "Randomly-generated comment for stress test #" + i,
                             rects:  [{"tl": [x, y], "br": [x + w, y - h]}]}, "add-comment");
        }
    }
}

CommentManager.prototype.fetchAllComments = function() {
    var self = this;
    var formData = {"review": window.reviewId};

    // Fetch new list from server and store for offline use.
    server.get_data(window.scriptURL + '/api/list-comments', { nocache: true, formdata: formData, onlineOnly: true, complete: function(p) {
        if(p && p.errorCode == 0) {
            self.commentDB.comments.bulkPut(p.comments).then(function() {
                self.refreshComments(false);
                self.applyFilters();
                if(self.goToComment) {
                    self.goToComment = false
                    self.pdfApp.linkService.navigateTo(location.hash.replace("#",""), true)
                }
            });

            if(p.status != "open") {
                if (!window.reviewClosed) new ModalDialog("dialog-closed-review");
                window.reviewClosed = true;
            }
        }
        else if(p && p.errorCode > 0) {
            $('#error-reason').html("Failed to fetch comment list: " + p.errorMsg);
            new ModalDialog("dialog-error");
        }
    }});
}

CommentManager.prototype.refreshComments = function(hideWhileLoading) {
    var self = this;
    var parentDiv = $('#comment-container');
    var progressDiv = $('#comment-status-loading');
    if(hideWhileLoading) {
        parentDiv.hide();
        progressDiv.show();
    }
    // This ensures the comments are sorted by the order they appear on the page.
    function commentOrdering(a, b) {
        if(a.rects == b.rects || (!a.rects.length && !b.rects.length)) return 0;        // Both null or same object
        if(a.rects && a.rects.length > 0 && (!b.rects || !b.rects.length)) return -1;   // A has coordinates, B does not. A comes first.
        if(b.rects && b.rects.length > 0 && (!a.rects || !a.rects.length)) return +1;   // B has coordinates, A does not. B comes first.
        if(!a.rects[0].tl || !b.rects[0].tl) return 0;                                  // Invalid configuration.
        return (a.rects[0].tl[1] < b.rects[0].tl[1]) ? +1 : -1;                         // PDF coordinates origin is bottom left.
    }
    function populateCommentList(comments) {
        comments.sort(commentOrdering).forEach(function(obj) {
            self.addComment(obj);
            if(self.statusList.indexOf(obj.status) < 0) self.statusList.push(obj.status);
            if(self.reviewerList.indexOf(obj.author) < 0) self.reviewerList.push(obj.author);
        });
        if(hideWhileLoading) setTimeout(function() {progressDiv.hide();parentDiv.show();}, 10);
    }
    return self.commentDB.comments.toArray(populateCommentList);
}

CommentManager.prototype.prettify = function(text) {
    var self = this;
    var output = text.replace(/&/g, "&amp;")
                     .replace(/</g, "&lt;")
                     .replace(/>/g, "&gt;")
                     .replace(/"/g, "&quot;")
                     .replace(/'/g, "&#039;");
    output = output.replace(/(https?:\/\/[^\s]+)/g, '<a href="$1" target="_blank">$1</a>')
    return output;
}

CommentManager.prototype.createCommentUI = function(comment, retries) {
    var self = this;
    if(retries > 1000) return;

    function commentReply(e) {
        $("#comment-msg").val("");
        $('#comment-guidelines').text('Please enter your response to that comment:');
        new ModalDialog("dialog-comment", function(dialog, button) {
            var txt = $("#comment-msg").val();
            if($(button).data("button") == "submit" && txt.length) {
                self.addComment({pageId:    e.data.comment.pageId,
                                 msg:       txt,
                                 owner:     true,
                                 unsync:    true,
                                 rects:     e.data.comment.rects,
                                 replyToId: e.data.comment.id}, "add-comment");
            }
        }, false);
        return cancel(e);
    }
    function commentDelete(e) {
        self.commentDB.comments.get(e.data.commentid).then(function(comment) {
            if(!comment.owner) return;
            $('#confirm-msg').html("This will delete the selected comment.<BR/><BR/>Is this really what you want to do?<BR/>");
            new ModalDialog("dialog-confirm", function(dialog, button) {
                if($(button).data("button") == "submit") {
                    comment.deleted = true;
                    self.addComment(comment, "delete-comment");
                }
            });
        });
        return cancel(e);
    }
    function commentStatus(e) {
        var link = $(this);
        self.commentDB.comments.get(e.data.commentid).then(function(comment) {
            function updateCommentStatus(status) {
                if(self.statusList.indexOf(status) < 0) self.statusList.push(status);
                comment.status = status;
                comment.unsync = true;
                self.addComment(comment, "update-comment-status");
            }
            if(comment.replyToId != undefined) return;   // Only allow status changes to top-level.
            var select = link.parent().find(".select-status");
            if(!select.length) {
                select = $("<SELECT>").addClass("select-status");
                for(var i = 0; i < self.statusList.length; i++) select.append($("<OPTION>").prop({value: self.statusList[i], selected: comment.status == self.statusList[i]}).text(self.statusList[i]));
                select.append($("<OPTION>").prop("value", "Custom").text("Custom"));
                link.parent().append(select);
            }
            link.hide();
            select.focus();
            select.on("change", function(evt) {
                var val = select.val();
                if(val == "Custom") {
                    $('#query-msg').html("Please select a custom status:")
                    new ModalDialog("dialog-query", function(dialog, button) {
                        if($(button).data("button") == "submit") {
                            var status = $('#query-value').val();
                            if(status && status.length > 0) updateCommentStatus(status);
                        }
                    });
                }
                else updateCommentStatus(val);
                link.show();
                select.remove();
            });
        });
        return cancel(e);
    }
    function commentUpdate(e) {
        self.commentDB.comments.get(e.data.comment.id).then(function(comment) {
            if(!comment.owner) return;
            $('#comment-guidelines').text('Please update your message below:');
            new ModalDialog("dialog-comment", function(dialog, button) {
                var msg = $("#comment-msg").val();
                if($(button).data("button") == "submit" && msg.length) {
                    $('#review-comment-' + comment.id + ' > div.comment-content').text(msg);
                    comment.msg    = msg;
                    comment.unsync = true;
                    self.addComment(comment, "update-comment-message");
                }
            }, false);
            $("#comment-msg").val(comment.msg);
        }, false);
        return cancel(e);
    }

    var parent;
    if(comment.deleted) parent = document.getElementById("review-comments-for-deletions");
    else if(comment.replyToId != undefined) parent = document.getElementById("review-comment-" + comment.replyToId);
    else parent = document.getElementById("review-comments-for-page-" + comment.pageId);
    if(!parent) {
        // Handle things that should nest but can't yet as their parent hasn't been created.
        setTimeout(function() {self.createCommentUI(comment, (retries ? (retries + 1) : 1));}, 1);
        return;
    }
    var div = document.createElement("div");
    div.className = "review-comment";
    if(comment.replyToId != undefined) $(parent).addClass("has-child");
    
    div.commentId   = comment.id;
    div.replyToId   = comment.replyToId;
    div.pageId      = comment.pageId;
    div.unread      = comment.unread;
    div.unsync      = comment.unsync;
    div.deleted     = comment.deleted;
    div.id = "review-comment-" + comment.id;
    if(document.getElementById(div.id)) return;     // Race condition, this card has already been created.
    if(comment.unread) $(div).addClass("new");
    if(comment.unsync) $(div).addClass("unsynchronised");
    var actions = $("<SPAN>").addClass("actions");
    if(!window.reviewClosed) actions.append($("<A>").text("Reply").on("click", {comment: comment}, commentReply)).append(" &nbsp; ")
    if(!window.reviewClosed && comment.owner) {
        actions.append($("<A>").text("Update").on("click", {comment: comment}, commentUpdate)).append(" &nbsp; ")
               .append($("<A>").text("Delete").on("click", {commentid: comment.id}, commentDelete).css({"float": "right", "color": "red"}));
    }
    if(comment.replyToId == undefined) actions.append($("<A>").text("Status").on("click", {commentid: comment.id}, commentStatus));
    if(comment.deleted) {
        parent.appendChild(div);
        $(div).hide();
    }
    else {
        $(div).append($("<B>").addClass("author").text(comment.author || "You").attr('title', "Comment from " + (new Date(comment.secs_UTC * 1000)).toLocaleString()))
              .append($("<SPAN>").addClass("status").text(comment.status == "None" ? "" : comment.status))
              .append($("<DIV>").addClass("comment-content").html(self.prettify(comment.msg || "")))
              .append(actions);
        parent.appendChild(div);
        $(div).on("mousedown", {commentid: comment.id}, self.onCommentContext)
              .on("click", {comment: comment}, function(e) {
                    var commentId   = e.data.comment.id;
                    var commentCard = $("#review-comment-" + e.data.comment.id);
                    if(commentCard.length) {
                        var p = commentCard.get(0);
                        while(p.replyToId != undefined) {
                            commentId = p.replyToId;
                            p         = document.getElementById("review-comment-" + commentId);
                        }
                        if(e.target && e.target.tagName == "A" && self.flashing == commentId) {
                            return; // Just return and let the hyperlink take care of itself
                        }
                    }
                    var offset = $(this).offset();
                    var cornerSize = parseInt($('#comment-container').css('font-size')) * 1.5;
                    if((e.pageX - offset.left) < cornerSize && (e.pageY - offset.top) < cornerSize && $(this).hasClass("has-child")) {   // Click on the "collapse" icon to collapse
                        $(this).toggleClass("collapsed");
                    }
                    else {
                        if(e.data.comment.pageId != self.pdfApp.currentPage) {  // Go to PDF page if not currently on that page
                            if(e.data.comment.rects && e.data.comment.rects.length > 0 && e.data.comment.rects[0].tl && e.data.comment.rects[0].tl.length) {
                                // Try to go the the right place on the page:
                                self.pdfApp.linkService.navigateTo(["direct", e.data.comment.pageId, e.data.comment.rects[0].tl[0], e.data.comment.rects[0].tl[1], e.data.comment.id]);
                            }
                            else {
                                // Otherwise default to the page it's on:
                                self.pdfApp.linkService.navigateTo("page=" + (e.data.comment.pageId + 1));
                            }
                        }
                        else if(window.history) {
                            history.pushState("comment="+e.data.comment.id, "Comment " + e.data.comment.id, self.pdfApp.linkService.getDestinationHash(
                                ["direct", e.data.comment.pageId, e.data.comment.rects[0].tl[0], e.data.comment.rects[0].tl[1], e.data.comment.id]
                            ));
                        }
                        self.selectComment(e.data.comment.id, false);
                    }
                    return cancel(e);
                })
              .on("dblclick", {comment: comment}, comment.owner ? commentUpdate : commentReply)
              .on("commentSelect", {comment: comment}, function(e) {
                  self.selectComment(e.data.comment.id, false);
              });
    }
}

CommentManager.prototype.addComment = function(comment, action) {
    var self = this;

    if(!comment.rects)  comment.rects = [];
    if(!comment.status) comment.status = "None";
    if(!comment.msg)    comment.msg = "";
    if(!comment.id)     comment.id = hasher({msg: comment.msg, replyToId: comment.replyToId, pageIndex: comment.pageIndex, rects: comment.rects, review: window.reviewId, seed: Math.random()});

    var card = document.getElementById('review-comment-' + comment.id);
    if(card) {    // Already created.
        var div = $(card);
        if(comment.unsync) div.addClass("unsynchronised");
        else               div.removeClass("unsynchronised");
        if(comment.unread) div.addClass("new");
        else               div.removeClass("new");
        card.unread  = comment.unread;
        card.unsync  = comment.unsync;
        card.deleted = comment.deleted;
        $('#review-comment-' + comment.id + ' > .author').text(comment.author || "You");
        $('#review-comment-' + comment.id + ' > .status').text(comment.status == "None" ? "" : comment.status);
        $('#review-comment-' + comment.id + ' > .comment-content').html(self.prettify(comment.msg || ""));
        card.unread = comment.unread;
        if(!action || action == "add-comment") return;
    }
    else if(!action || action == "add-comment") self.createCommentUI(comment);
    if(!action) return;
    self.commentDB.comments.put(comment);

    var formData = {"review": window.reviewId};
    var failure_msg;
    if(action == "add-comment") {
        formData.comment = comment;
        failure_msg = "Failed to upload comment: ";
        self.redraw(comment.pageId);
    }
    else if(action == "delete-comment") {
        formData.commentid = comment.id;
        failure_msg = "Failed to delete comment: ";
        $('#review-comment-' + comment.id).remove().get(0).deleted = true;
        self.redraw(comment.pageId);
    }
    else if(action == "update-comment-status") {
        formData.commentid = comment.id;
        formData.status    = comment.status;
        failure_msg = "Failed to update comment status: ";
    }
    else if(action == "update-comment-message") {
        formData.commentid = comment.id;
        formData.message   = comment.msg;
        failure_msg = "Failed to update comment message: ";
    }
    else throw new Error("Unhandled add-comment action: " + action);
    self.applyFilters();

    server.get_data(window.scriptURL + '/api/' + action, { nocache: true,
                                        formdata: formData,
                                        complete: function(p) {
        if(!p || p.errorCode > 0) {
            $('#error-reason').html(failure_msg + (p ? p.errorMsg : ""));
            new ModalDialog("dialog-error");
        }
        else {
            // Uploaded, remove pending.
            $('#review-comment-' + comment.id).removeClass("unsynchronised");
            self.commentDB.comments.update(comment.id, {unsync: false});
        }
    }});
}

CommentManager.prototype.redraw = function(pageId, pageContainer) {
    var self = this;
    if(!pageContainer) pageContainer = self.pdfApp.getPageContainer(pageId);
    if(!pageContainer || !pageContainer.rendered) return;  // Page is not ready yet -- stop

    var reviewLayer = pageContainer.reviewLayer;
    var viewport    = pageContainer.viewport;
    if(!viewport) return;   // Page not yet ready -- stop

    self.commentDB.comments.where("pageId").equals(pageId).each(function(comment) {
        var pdfCommentDivs = $('.pdf-comment-div-for-' + comment.id);
        if(!pdfCommentDivs.length && comment.rects && comment.rects.length > 0) {
            var boundingRect = {};
            for(var m = 0; m < comment.rects.length; m++) {
                var d = document.createElement("div");
                var q = comment.rects[m];
                var tl_rect = viewport.convertToViewportPoint(q.tl[0], q.tl[1]);
                d.className = comment.type + " pdf-comment-div-for-" + comment.id;
                d.style.top     = tl_rect[1] + "px";
                d.style.left    = tl_rect[0] + "px";
                if(comment.type == "highlight" || comment.type == "strike") {
                    var br_rect = viewport.convertToViewportPoint(q.br[0], q.br[1]);
                    d.style.height  = (br_rect[1] - tl_rect[1]) + "px";
                    d.style.width   = (br_rect[0] - tl_rect[0]) + "px";
                    boundingRect.top    = boundingRect.top    ? Math.min(boundingRect.top,    tl_rect[1]) : tl_rect[1];
                    boundingRect.left   = boundingRect.left   ? Math.min(boundingRect.left,   tl_rect[0]) : tl_rect[0];
                    boundingRect.bottom = boundingRect.bottom ? Math.max(boundingRect.bottom, br_rect[1]) : br_rect[1];
                    boundingRect.right  = boundingRect.right  ? Math.max(boundingRect.right,  br_rect[0]) : br_rect[0];
                }
                reviewLayer.appendChild(d);

                function cancelBubbleDrag() {
                    $(document).off("mousemove.bubble");
                    $(document).off("mouseup.bubble");
                }

                if(comment.type == "comment") {
                    boundingRect.top    = tl_rect[1] - d.clientHeight/2;
                    boundingRect.bottom = tl_rect[1] + d.clientHeight/2;
                    boundingRect.left   = tl_rect[0] - d.clientWidth/2;
                    boundingRect.right  = tl_rect[0] + d.clientWidth/2;

                    $(d).on("mousedown", {bubble: d}, function(e) {
                        var parentOffset = $(this).parent().offset();
                        var position = $(this).position();
                        $(document).on("mousemove.bubble", {
                            bubble: e.data.bubble,
                            startX: position.left,
                            startY: position.top,
                            mouseX: e.pageX,
                            mouseY: e.pageY
                        }, function(e) {
                            cancel(e);
                            e.data.bubble.style.top  = (e.data.startY + (e.pageY - e.data.mouseY)) + "px";
                            e.data.bubble.style.left = (e.data.startX + (e.pageX - e.data.mouseX)) + "px";
                        });
                        $(document).on("mouseup.bubble", {}, cancelBubbleDrag);
                    });
                }

                // Add interactive features
                $(d).on("mouseup", {commentId: comment.id, cancelBubble: (comment.type == "comment")}, function(e) {
                    // Cancel draggable bubbles
                    if(e.data.cancelBubble) cancelBubbleDrag();

                    // If the current tool allows insertion of comments, update the current comment.
                    if(window.mouseTools.activeTool == "highlight" || window.mouseTools.activeTool == "strike" || window.mouseTools.activeTool == "comment") {
                        self.selectComment(e.data.commentId, true, true);
                        return cancel(e);
                    }
                    else self.selectComment(e.data.commentId, true);
                });
            }
            var d = document.createElement("div");
            d.className     = "finder";                         // The finders are hidden by default
            d.id            = "reviewlayer-comment-" + comment.id;
            d.style.top     = (boundingRect.top - 10) + "px";
            d.style.left    = "-20px";
            d.style.height  = (boundingRect.bottom - boundingRect.top + 20) + "px";
            d.style.width   = "1px";
            reviewLayer.appendChild(d);
        }

        // All div structures are created, now shiw/hide as necessary!
        var div = $('#review-comment-' + comment.id);
        pdfCommentDivs = $('.pdf-comment-div-for-' + comment.id);
        if(!div.length || div.hasClass("filteredOut") || comment.deleted) {
            pdfCommentDivs.hide();
            $('#reviewlayer-comment-' + comment.id).hide();
        }
        else {
            pdfCommentDivs.show();
            if(self.flashing == comment.id) {
                $('#reviewlayer-comment-' + comment.id).show();
                pdfCommentDivs.addClass("selectedComment");
            }
        }
    })["catch"](function(e){throw new Error(e);});
}

CommentManager.prototype.selectComment = function(commentId, scrollComments, dblClickAction) {
    var self = this;
    var commentCard = $("#review-comment-" + commentId);
    if(!commentCard.length) return;     // Not ready yet.

    // If this is a new comment, send a read notification
    if(commentCard.get(0).unread) {
        commentCard.removeClass("new");
        commentCard.unread = false;
        self.commentDB.comments.update(commentId, {unread: false});
        var formData = {
            "review":   window.reviewId,
            "id":       commentId,
            "as":       "read"};
        server.get_data(window.scriptURL + '/api/user-mark-comment', { nocache: true, formdata: formData });    // Fire-and-forget
    }

    // Now actually select the parent comment
    var parent = commentCard.get(0);
    while(parent.replyToId != undefined) {
        commentId = parent.replyToId;
        parent    = document.getElementById("review-comment-" + commentId);
    }
    var commentSel = $("#reviewlayer-comment-" + commentId);

    // Scroll card into view if not yet visible...
    if(scrollComments) {
        var commentCardParent = $(self.commentContainer).parent();
        var cardOffsetTop = commentCard.position().top;
        var visibleRange  = [0, commentCardParent.height()];
        // Determine if the commentCard is visible or not, scroll as necessary:
        if((cardOffsetTop < visibleRange[0]) || ((cardOffsetTop + commentCard.height()) > visibleRange[1])) {
            var target = cardOffsetTop + commentCardParent.scrollTop() - 100;
            commentCardParent.animate({ scrollTop: target + "px"}, 200);
        }
    }
    $('.selectedComment').removeClass("selectedComment");
    $('.pdf-comment-div-for-' + commentId).addClass("selectedComment");
    $(".reviewLayer div.finder").hide();
    $("#comment-container div.review-comment.selected").removeClass("selected");
    commentCard.addClass("selected");
    commentSel.show();
    self.flashing = commentId;

    // Scroll element into view if needed (and supported by the browser -- this will only work on Chrome)
    var scrollView = $('.selectedComment')[0];
    if(scrollView && scrollView.scrollIntoViewIfNeeded) scrollView.scrollIntoViewIfNeeded();

    if(dblClickAction) {
        commentCard.trigger("dblclick");
    }
}

CommentManager.prototype.applyFilters = function() {
    var self = this;
    var count = 0;
    var pages = {};
    var regexp = new RegExp(self.filters.txt || ".*", "i");

    // Phase 1: update gui to reflect filter state
    var filtersApplied = self.filters.txt.length || self.filters.unreadOnly || self.filters.status.length || self.filters.reviewers.length;
    if(filtersApplied) self.filterButton.addClass("active");
    else self.filterButton.removeClass("active");

    // Phase 2: hide all comments
    $('.review-comment').addClass("filteredOut").removeClass("filteredIn");

    // Phase 3: show any comments that match
    self.commentDB.comments.each(function(comment) {
        pages[comment.pageId] = comment.pageId;
        if(comment.deleted) return;
        var isTopLevel  = comment.replyToId == undefined;
        // The match filters AND all properties, ORed with a text match. In addition:
        //  - if the unread status matches a reply, it trickles up to the parent
        //  - status only matches parents, but then shows all replies
        //  - reviewer only matches parents, but then shows all replies
        var txtMatch    = comment.msg.match(regexp);
        var unreadMatch = !self.filters.unreadOnly || comment.unread;
        var statusMatch = !self.filters.status.length || !isTopLevel || self.filters.status.indexOf(comment.status) < 0;
        var reviewMatch = !self.filters.reviewers.length || !isTopLevel || !comment.author || self.filters.reviewers.indexOf(comment.author) < 0;
        if(isTopLevel) count ++;

        if(self.flashing == comment.id || (txtMatch && unreadMatch && statusMatch && reviewMatch)) {
            var card = document.getElementById('review-comment-' + comment.id);
            if(isTopLevel) $(card).addClass("topLevel");
            while(((txtMatch && self.filters.txt.length > 0) || (self.filters.unreadOnly && unreadMatch)) && card && card.replyToId != undefined) {
                $(card).removeClass("filteredOut").addClass("filteredIn");
                card = document.getElementById('review-comment-' + card.replyToId);      // Bubble-up to top-level
                if(card.deleted) return;
            }
            $(card).removeClass("filteredOut").addClass("filteredIn");
        }
    }).then(function() {
        // Refresh PDF pages as necessary
        $('.review-comment.filteredOut').hide();
        $('.review-comment.filteredIn').show();
        for(var page in pages) self.redraw(pages[page]);
        $('#comment-status-msg').text("Showing " + $('.review-comment.filteredIn.topLevel').length + " of " + count);
    });
}
