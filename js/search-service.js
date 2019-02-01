/*
 * Javascript functions to help with search-related services.
 * Francois Botman, 2017.
 */

function SearchToolUI(pdfApp) {
    var self              = this;
    self.pdfApp           = pdfApp;
    self.bookmarks        = $('#sidebar-left-bookmarks');
    self.searchBarResults = $('#sidebar-left-search-results');
    self.searchWrap       = $('#search-tool-wrap');
    self.searchButtonPrev = $('#button-search-prev');
    self.searchButtonNext = $('#button-search-next');

    function openSearch() {
        if(!self.tool) {
            self.bookmarks.hide();
            self.searchBarResults.show();
            window.sidebarLeft.show();
            self.searchBarResults.empty();
            self.searchBarResults.append($('<DIV>').html("Search results will appear here...").addClass("search-placeholder"));

            $("#button-left-sidebar-toggle").addClass("active");
            self.tool = new ModalTool('search-tool', $('#button-search-toggle'), function(e) {
                // Start a new search
                self.searchBarResults.empty();
                $(".textLayer .searchResult").remove();
                self.searchWrap.text("");
                self.searchResultIndex = undefined;
                var resultId = 0;

                self.search($('#search-tool-query').val(),
                            $('#search-tool-config-case').is(':checked'),
                            $('#search-tool-config-regex').is(':checked'),
                            function(result) {  // Results come in one-by-one here as they arrive.
                                var resultDiv = document.createElement("DIV");
                                $(resultDiv).html("<I>" + (result.pageId + 1) + ":</I> &nbsp; " + result.matchStr)
                                            .on("click", {id: resultId}, function(e) {
                                    self.findId(e.data.id);
                                    return cancel(e);
                                });
                                self.searchBarResults.append(resultDiv);
                                self.highlight(resultId++, result);
                            }).then(function() {    // All results retrieved
                                if(self.results.length == 0) {
                                    self.searchWrap.text("No results found");
                                    self.searchButtonPrev.hide();
                                    self.searchButtonNext.hide();
                                }
                                else {
                                    self.searchButtonPrev.show();
                                    self.searchButtonNext.show();
                                }
                            });
            });
            $(window).on("pdf-scale", function() {self.highlightAll();});
        }
        else self.tool.select();
        $('#button-search-toggle').addClass("active");
    }
    function closeSearch() {
        if(self.tool) self.tool.close();
        self.tool = null;
        self.searchButtonPrev.hide();
        self.searchButtonNext.hide();
        self.searchBarResults.hide();
        self.bookmarks.show();
        $(".textLayer .searchResult").remove();
        $('#button-search-toggle').removeClass("active");
        $(window).off("pdf-scale");
    }

    // Register UI stuff
    $(document).on("keydown.search", function(e) {
        if      (e.which == 70 && (e.ctrlKey || e.metaKey)) openSearch(); // CTRL+F
        else if (e.which == 71 && (e.ctrlKey || e.metaKey)) openSearch(); // CTRL+G
        else if (e.which == 114) { // F3 (+/- SHIFT)
            if(self.results && self.results.length) {
                if(!e.shiftKey) self.findNext();
                else self.findPrevious();
            }
            else openSearch();
        }
        else return ;
        return cancel(e);
    });
    $('#button-search-toggle').on("click", function(e) {
        var button = $(e.target);
        if(button.hasClass("active")) closeSearch();
        else openSearch();
    });
    self.searchButtonPrev.on("click", function(e) {self.findPrevious();});
    self.searchButtonNext.on("click", function(e) {self.findNext();});
}

SearchToolUI.prototype.search = function(query, matchCase, regex, onresult) {
    var self = this;
    self.results = [];
    if(!query) return new Promise(function(){});
    var progressbar = $(document.body.appendChild(document.createElement("DIV"))).addClass("progress").css("width", "0px");
    var total = 1;
    var done = 0;

    // We need to escape regex characters for non-regex queries
    if(!regex) query = query.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&').replace(/\s/g, '\\s+');
    self.searchWrap.text("");
    try {
        self.searchQuery = new RegExp(query.replace('\\\\', '\\\\\\\\'), matchCase ? "" : "i")
    } catch(err) {
        self.searchWrap.text("Invalid regex");
    }

    function _textArraySearch(pageId, textLines) {
        for(var i = 0; i < textLines.length; i++) {
            if(textLines[i].str.match(self.searchQuery)) {
                var result = {pageId:    pageId,
                              str:       textLines[i].str,
                              matchStr:  textLines[i].str.replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(self.searchQuery, "<B>$&</B>"),
                              transform: textLines[i].transform,
                              fontName:  textLines[i].fontName};
                self.results.push(result);
                if(onresult) onresult(result);
            }
        }
        done++;
        progressbar.css("width", (100.0 * done / total) + "%");
    }

    function _searchPage(pageId) {
        return self.pdfApp.getPageText(pageId).then(function(text) {   // Get text on page
            _textArraySearch(pageId, text.items);
        }, function() {throw new Error("Unable to get text on pdf page.");});
    }

    return new Promise(function(resolve) {
        var textPromises = [];
        if(!self.pdfApp.pdf) throw new Error("PDF document is not read.");
        total = self.pdfApp.pdf.numPages;
        for (var page = 0; page < self.pdfApp.pdf.numPages; page++) {
            textPromises.push(_searchPage(page));
        }
        // Wait for search to complete
        Promise.all(textPromises).then(function() {
            progressbar.remove();
            resolve();
        }, function() {throw new Error("Unable to resolve search requirements.");});
    });
}

SearchToolUI.prototype.highlight = function(id, resultObj) {
    var self = this;
    var container = self.pdfApp.getPageContainer(resultObj.pageId);
    self.pdfApp.getPageText(resultObj.pageId).then(function(textCotent) {
        var viewport = container.viewport;
        var div      = document.createElement("DIV");
        var tx       = PDFJS.Util.transform(viewport.transform, resultObj.transform);
        var angle    = Math.atan2(tx[1], tx[0]);
        var style    = textCotent.styles[resultObj.fontName];
        div.id       = "search-result-" + id;
        if (style.vertical) angle += Math.PI / 2;
        var fontHeight = Math.sqrt((tx[2] * tx[2]) + (tx[3] * tx[3]));
        var fontAscent = fontHeight;
        if(style.ascent)       fontAscent = style.ascent * fontAscent;
        else if(style.descent) fontAscent = (1 + style.descent) * fontAscent;

        var divStyles = {
            'font-size':      fontHeight,
            'font-family':    style.fontFamily
        };
        if(angle === 0) {
            divStyles.left = tx[4] + "px";
            divStyles.top  = (tx[5] - fontAscent) + "px";
        }
        else {
            divStyles.left = (tx[4] + (fontAscent * Math.sin(angle))) + "px";
            divStyles.top  = (tx[5] - (fontAscent * Math.cos(angle))) + "px";
        }
        container.textLayer.appendChild(div);
        $(div).addClass("searchResult").css(divStyles).html(resultObj.matchStr);
        if(id == self.searchResultIndex) $(div).addClass("selected");
    });
}

SearchToolUI.prototype.highlightAll = function() {
    $(".textLayer .searchResult").remove();
    for(var i = 0; i < this.results.length; i++) this.highlight(i, this.results[i]);
}

SearchToolUI.prototype.findId = function(id) {
    var self = this;
    if(!self.results || !self.results.length) return;
    if(id < 0 || id >= self.results.length) {
        id = (id < 0) ? (self.results.length - 1) : 0;
        self.searchWrap.text("Search wrapped from start");
    }
    else self.searchWrap.text("");

    var result = self.results[id];
    if(self.pdfApp.currentPage != result.pageId) {
        self.pdfApp.linkService.navigateTo("page=" + (result.pageId + 1));
        self.highlightAll();
    }
    else $('.searchResult.selected').removeClass("selected");
    $("#search-result-" + id).addClass("selected");
    self.searchResultIndex = id;
    return id;
}

SearchToolUI.prototype.findNext = function() {
    var self = this;
    if(self.searchResultIndex === undefined) self.searchResultIndex = -1;
    self.searchResultIndex = self.findId(self.searchResultIndex + 1);
}

SearchToolUI.prototype.findPrevious = function() {
    var self = this;
    if(self.searchResultIndex === undefined) self.searchResultIndex = -1;
    self.searchResultIndex = self.findId(self.searchResultIndex - 1);
}