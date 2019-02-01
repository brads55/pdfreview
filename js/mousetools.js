/*
 * Javascript functions to help with mouse tools.
 * Francois Botman, 2017.
 */


function MouseTools(pdfApp) {
    var self = this;
    self.pdfView = $("#pdfview");
    self.pdfApp  = pdfApp;
    self.activeTool;
    self.tools = {
        'pointer':      {button: $('#button-mode-pointer'),   keyCode: 49 /* 1 */, start: self._pointer, end: self.endTool},
        'grab':         {button: $('#button-mode-grab'),      keyCode: 54 /* 6 */, start: self._grab, end: self.endTool},
        'highlight':    {button: $('#button-mode-highlight'), keyCode: 50 /* 2 */, start: self._highlight, end: self.endTool},
        'strike':       {button: $('#button-mode-strike'),    keyCode: 53 /* 5 */, start: self._strike, end: self.endTool},
        'comment':      {button: $('#button-mode-comment'),   keyCode: 52 /* 4 */, start: self._comment, end: self.endTool},
        'rectangle':    {button: $('#button-mode-rectangle'), keyCode: 51 /* 3 */, start: self._rectangle, end: self.endTool}
    }
    for(var t in self.tools) {
        self.tools[t].button.on("mousedown", {tool: t}, function(e) {
            if(e.which != 1) return;    // left-click only
            self.selectTool(e.data.tool);
        });
    }

    // Register window shortcuts
    $(window).on("keydown.mousetools", function(e) {
        for(var t in self.tools) {
            if(e.which == self.tools[t].keyCode && (e.ctrlKey || e.metaKey)) {
                self.selectTool(t);
                return cancel(e);
            }
        }
    });
    // Register tool palette
    self.pdfView.on("mousedown", function(e) {
        if(e.which == 3) {
            if(!window.reviewClosed) {
                self.paletteActive    = true;
                self.paletteSelection = {sel: window.getSelection ? window.getSelection() : document.selection, page: e.target};
                self.selectTool("pointer");     // Cancel tool
                $('#tool-palette').show().css({left: e.pageX - 100, top: e.pageY - 100});
                $('#palette-status').show().css({left: e.pageX - 100, top: e.pageY + 110});
                $("#palette-status").html($('#tool-palette .centre').prop("title"));
            }
            $("#tool-palette > div").on("mouseover", function(e) {
                $("#palette-status").html($(e.target).prop("title"));
            }).on("mouseout", function(e) {
                $("#palette-status").html("");
            });
            return cancel(e);
        }
    });
    $(window).on("contextmenu", function(e) {
        if(self.paletteActive) return cancel(e);
    });
    $(window).on("mouseup", function(e) {
        if(self.paletteActive) {
            var tool = $(e.target).data("tool");
            $('#tool-palette').hide().css({left: 0, top: 0});
            $('#palette-status').hide().css({left: 0, top: 0});
            $("#tool-palette > div").off("mouseover").off("mouseout");
            setTimeout(function() { // hack to avoid context menu on existing selection.
                if(tool in self.tools) self.selectTool(tool);
                self.paletteActive    = false;
                self.paletteSelection = false;
            }, 1);
            return cancel(e);
        }
    });

    // select default tool
    self.selectTool('pointer');
}

MouseTools.prototype.selectTool = function(tool) {
    var self = this;

    if(self.activeTool) {
        self.pdfView.off("mousedown.mousetool").off("mouseup.tool").off("mousemove.tool");
        self.tools[self.activeTool].end.call(self);
    }
    self.activeTool = tool || "pointer";

    for(var t in self.tools) self.tools[t].button.removeClass("active");
    self.toolActive = false;
    self.tools[self.activeTool].button.addClass("active");
    self.tools[self.activeTool].start.call(self);
}

MouseTools.prototype.endTool = function() {
    var self = this;
    $(".page").off("click.mousetool")
              .off("mousedown.mousetool")
              .off("mouseup.mousetool")
              .removeClass("default-tool")
              .removeClass("highlight-tool")
              .removeClass("rectangle-tool")
              .removeClass("strike-tool")
              .removeClass("comment-tool")
              .removeClass("grab-tool");
    $(window).off("click.mousetool")
             .off("mousedown.mousetool")
             .off("mouseup.mousetool")
             .off("mousemove.mousetool");
    if(self.temporaryDiv) self.temporaryDiv.remove();
    self.temporaryDiv = false;
}

MouseTools.prototype._selectionToolStart = function() {
    var self = this;

    function doSelectionTask(sel, page) {
        var padding  = 0.1;
        var elements = [];
        var selectionValid = false;

        // Get the viewport
        while(page && !page.viewport) page = page.parentElement;
        if(!page) return;
        var viewport = page.viewport;
        var offset   = $(page).offset();

        // Iterate over selection
        var previous = null;
        for(var i = 0; i < sel.rangeCount; i++) {
            var rects = sel.getRangeAt(i).getClientRects();
            for(var q = 0; q < rects.length; q++) {
                var rect  = rects[q];
                var tlx = (rect.left - offset.left - padding);
                var tly = (rect.top - offset.top - padding);
                var brx = (rect.left - offset.left + rect.width  + 2*padding);
                var bry = (rect.top  - offset.top  + rect.height + 2*padding);
                if((brx - tlx) > 1 && (bry - tly) > 1) selectionValid = true;

                // Merge elements if on the same line to reduce #rectangles
                if(previous && Math.abs(tly - previous) < 10) {
                    elements[elements.length - 1] = {
                        tl: [Math.min(elements[elements.length - 1].tl[0], tlx), Math.min(elements[elements.length - 1].tl[1], tly)],
                        br: [Math.max(elements[elements.length - 1].br[0], brx), Math.max(elements[elements.length - 1].br[1], bry)]
                    }
                }
                else {
                    elements.push({
                        tl: [tlx, tly],
                        br: [brx, bry]
                    });
                }
                previous = tly;
            }
        }

        // Convert all rectangles to pdf viewport.
        for(var i = 0; i < elements.length; i++) {
            elements[i] = {
                tl: viewport.convertToPdfPoint(elements[i].tl[0], elements[i].tl[1]),
                br: viewport.convertToPdfPoint(elements[i].br[0], elements[i].br[1])
            }
        }

        // Clear selection
        if (sel) {
            if(sel.removeAllRanges) sel.removeAllRanges();
            else if(sel.empty) sel.empty();
        }

        // Create dialog to submit comment with message
        if(selectionValid && elements.length) {
            $("#comment-msg").val("");
            $('#comment-guidelines').text('Please enter an associated comment (optional).');
            new ModalDialog("dialog-comment", function(dialog, button) {
                if($(button).data("button") == "submit") {
                    self.pdfApp.commentService.addComment({pageId: page.pageIndex,
                                                           owner:  true,
                                                           unsync: true,
                                                           type:   self.activeTool,
                                                           msg:    $("#comment-msg").val(),
                                                           rects:  elements}, "add-comment");
                }
            });
        }
    }
    
    $(".page").on("mouseup.mousetool", function(e) {
        if(e.which != 1) return;    // left-click only
        var page     = e.target;
        var sel      = window.getSelection ? window.getSelection() : document.selection;
        doSelectionTask(sel, page);
    });

    if(self.paletteSelection) {
        // There might be an active selection that the user was to act upon?
        doSelectionTask(self.paletteSelection.sel, self.paletteSelection.page);
    }
}

MouseTools.prototype._pointer = function() {
    $('.page').addClass("default-tool");
}

MouseTools.prototype._grab = function() {
    var self = this;

    $('.page').addClass("grab-tool");
    self.pdfView.on("mousedown.mousetool", function(e) {
        if(e.which != 1) return;    // left-click only
        self.toolActive = true;
        self.clickRect = {top: e.pageY, left: e.pageX};
        $('.page').addClass("grabbing");
        return cancel(e);
    })
    .on("mouseup.tool", function(e) {
        if(e.which != 1) return;    // left-click only
        self.toolActive = false;
        self.clickRect = {top: e.pageY, left: e.pageX};
        $('.page').removeClass("grabbing");
    })
    .on("mousemove.tool", function(e) {
        if(!self.toolActive) return;
        var curScroll = {
            top:  self.pdfView.scrollTop(),
            left: self.pdfView.scrollLeft()
        }
        var curRect = {top: e.pageY, left: e.pageX};
        self.pdfView.scrollTop(curScroll.top   + self.clickRect.top  - curRect.top)
                    .scrollLeft(curScroll.left + self.clickRect.left - curRect.left);
        self.clickRect = curRect;
    });
}

MouseTools.prototype._highlight = function() {
    this._selectionToolStart();
    $(".page").addClass("highlight-tool");
}

MouseTools.prototype._strike = function() {
    this._selectionToolStart();
    $(".page").addClass("strike-tool");
}

MouseTools.prototype._comment = function() {
    var self = this;
    var iconSize = 20;
    $(".page").addClass("comment-tool").on("click.mousetool", function(e) {
        if(e.which != 1) return;    // left-click only
        var clickRect = {top: e.pageY, left: e.pageX};
        var page = $(this);
        while(page.get(0) && !page.hasClass("page")) page = page.parent();
        if(!page.get(0)) return;
        var offset = page.offset();
        var cx = clickRect.left - offset.left;
        var cy = clickRect.top  - offset.top;
        var viewport = page.get(0).viewport;
        var elements = [{
            tl: viewport.convertToPdfPoint(cx, cy)
        }];

        // Create comment and submit
        $("#comment-msg").val("");
        $('#comment-guidelines').text('Please enter an associated comment (optional).');
        new ModalDialog("dialog-comment", function(dialog, button) {
            if($(button).data("button") == "submit") {
                self.pdfApp.commentService.addComment({pageId: page.get(0).pageIndex,
                                                       type:   "comment",
                                                       unsync: true,
                                                       owner:  true,
                                                       msg:    $("#comment-msg").val(),
                                                       rects:  elements}, "add-comment");
            }
        });
    });
}

MouseTools.prototype._rectangle = function() {
    var self = this;
    var clickRect;
    var div;

    function getPageDiv(parent) {
        var page = $(parent);
        while(page.get(0) && !page.hasClass("page")) page = page.parent();
        return page;
    }

    function getRelativeRect(e, page) {
        var mouse = {top: e.pageY, left: e.pageX};
        var offset = $(page).offset();
        var curScroll = {
            top:  self.pdfView.scrollTop(),
            left: self.pdfView.scrollLeft()
        };
        var cx = mouse.left - offset.left;
        var cy = mouse.top  - offset.top;
        return {top: cy, left: cx};
    }

    $(".page").addClass("rectangle-tool").on("mousedown.mousetool", function(e) {
        if(e.which != 1) return;    // left-click only
        var page  = getPageDiv(this);
        if(!page.get(0)) return;
        clickRect = getRelativeRect(e, page);
        div = $("<div>").addClass("highlight-rectangle").css({top: clickRect.top + "px", left: clickRect.left + "px", width: "0px", height: "0px"});
        self.temporaryDiv = div;
        page.append(div);

        $(window).on("mousemove.mousetool", function(e) {
            var newRect = getRelativeRect(e, page);
            div.css({top:       Math.min(clickRect.top, newRect.top),
                     height:    Math.abs(clickRect.top - newRect.top),
                     left:      Math.min(clickRect.left, newRect.left),
                     width:    Math.abs(clickRect.left - newRect.left)});
        }).on("mouseup.mousetool", function(e) {
            if(e.which != 1) return;    // left-click only
            $(window).off("mousemove.mousetool").off("mouseup.mousetool");
            var newRect = getRelativeRect(e, page);
            var viewport = page.get(0).viewport;
            var elements = [{
                tl: viewport.convertToPdfPoint(Math.min(clickRect.left, newRect.left), Math.min(clickRect.top, newRect.top)),
                br: viewport.convertToPdfPoint(Math.max(clickRect.left, newRect.left), Math.max(clickRect.top, newRect.top))
            }];
            div.remove();

            // Create comment and submit
            $("#comment-msg").val("");
            $('#comment-guidelines').text('Please enter an associated comment (optional).');
            new ModalDialog("dialog-comment", function(dialog, button) {
                if($(button).data("button") == "submit") {
                    self.pdfApp.commentService.addComment({pageId: page.get(0).pageIndex,
                                                           type:   "highlight",
                                                           unsync: true,
                                                           owner:  true,
                                                           msg:    $("#comment-msg").val(),
                                                           rects:  elements}, "add-comment");
                }
            });
        });

        return cancel(e);
    });
}