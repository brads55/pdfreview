/*
 * Javascript functions to handle the main PDF review tool.
 * Francois Botman, 2017.
 */

function PDFReviewApplication(pdfUrl, config) {
    this.config = {
        preloadRadius:      (config && config.preloadRadius) || 3,
        destroyRadius:      (config && config.destroyRadius) || 20,
        zoomIncrement:      0.25
    }
    if(this.config.destroyRadius < this.config.preloadRadius) this.config.destroyRadius = this.config.preloadRadius - 1;

    pdfjsLib.GlobalWorkerOptions.workerSrc = 'js/pdf.worker.js'

    this.pdfUrl         = pdfUrl;
    this.progressbar    = $(document.body.appendChild(document.createElement("DIV"))).addClass("progress").css("width", "0px");
    this.scale          = 1.0;
    this.pdfView        = $("#pdfview");
    this.currentPage    = -1;
    this.isPasswordProtected = false;
}

PDFReviewApplication.prototype.loadPDF = function() {
    var self = this;
    return new Promise(function(resolve) {
        // Create an instance of the PDFJS library
        // The following options are used:
        //  - url: what is the url for the pdf file
        //  - cMapUrl / cMapPacked: where the cMaps are located
        //  - disableAutoFetch / disableStream / disableRange: this avoids making use of Ranged requests, which is not supported by ServiceWorkers used in offline mode
        var load = pdfjsLib.getDocument({url: self.pdfUrl, cMapUrl: 'cmaps/', cMapPacked: true, disableAutoFetch: true, disableStream: true, disableRange: true});

        // Incorrect password, ask for a new one.
        load.onPassword = function(updatePassword, reason) {
            self.isPasswordProtected = true;
            if(reason == pdfjsLib.PasswordResponses.INCORRECT_PASSWORD) $('#password-reason').html('<SPAN style="color:red;">The specified password is incorrect.</SPAN>')
            new ModalDialog("dialog-password", function(dialog, button) {
                var password = $('#password-prompt').val()
                if($(button).data("button") != "submit") $('#password-reason').html("<BR/>There's no ESCAPE!<BR/><BR/>If you're really lost, try going <A HREF=\"/\">back to the main page</A>.<BR/>")
                updatePassword(password);
            });
        }
        load.onProgress = function(progress) {
            self.progressbar.css("width", (100.0 * progress.loaded / progress.total) + "%");
        }
        load.then(function(pdf) {
            self._documentLoaded.call(self, pdf);
            resolve(self);
        }, function(exception) {
            // Error when loading PDF
            var message = ""
            if(exception && exception.message) message = exception.message + "<BR/><BR/>";
            if(exception instanceof pdfjsLib.InvalidPDFException)               message += 'Invalid or corrupted PDF file.<BR/><BR/>I mean it looks good, but it tastes really bad :/<BR/><BR/>';
            else if (exception instanceof pdfjsLib.MissingPDFException)         message += 'The requested review PDF could not be located. Like, anywhere.<BR/><BR/>';
            else if (exception instanceof pdfjsLib.UnexpectedResponseException) message += 'Unexpected server response.<BR/><BR/>That one is on me.<BR/><BR/>';
            $('#error-reason').html(message);
            new ModalDialog("dialog-error");
        });
    });
}

PDFReviewApplication.prototype._documentLoaded = function(pdf) {
    var self = this;
    self.pdf = pdf;
    self.linkService    = new PDFLinkService(self);
    self.commentService = new CommentManager(self, document.getElementById("comment-container"));
    self.progressbar.remove();
    self.linkService.setDocument(pdf);

    // Create containers for all pages
    self.pageContainers = Array(pdf.numPages)
    for(var page = 0; page < pdf.numPages; page++) {
        var e = document.createElement("DIV")
        e.pageIndex = page;
        $(e).addClass("page");
        self.pageContainers[page] = e;
        self.pdfView.append(self.pageContainers[page]);
        e.textLayer = document.createElement("DIV")
        $(e.textLayer).addClass("textLayer");
        $(e).append(e.textLayer);
        e.reviewLayer = document.createElement("DIV")
        $(e.reviewLayer).addClass("reviewLayer");
        $(e).append(e.reviewLayer);
        e.annotationLayer = document.createElement("DIV")
        $(e.annotationLayer).addClass("annotationLayer");
        $(e).append(e.annotationLayer);
    }

    if(window.reviewClosed) {
        $('.page').prepend($('<div>').addClass("sticker"));
    }

    // Monitor scroll and update scale
    watchScroll(self.pdfView.get(0), function() {self.redraw.call(self);});
    self.setScale(self.scale);

    // Show bookmarks (if any)
    pdf.getOutline().then(function(outline) {
        self._showOutline(outline);
    });
}

PDFReviewApplication.prototype._showOutline = function(outlines, parent) {
    var self = this;
    if(!parent) parent = $(document.getElementById("sidebar-left-bookmarks"));
    if(!outlines) return;
    for(var i = 0; i < outlines.length; i++) {
        var outlineItem = outlines[i];
        var div = document.createElement("DIV");
        parent.append(div);
        div = $(div);
        div.addClass("bookmark-link");
        div.text(outlineItem.title);
        if(outlineItem.items && outlineItem.items.length > 0) {
            div.addClass("has-child").addClass("collapsed");
            self._showOutline(outlineItem.items, div);
        }
        div.on("click", {dest: outlineItem.dest}, function(e) {
            var offset = $(this).offset();
            var cornerSize = 20;
            if((e.pageX - offset.left) < cornerSize && (e.pageY - offset.top) < cornerSize) {   // Click on the "collapse" icon to collapse
                $(this).toggleClass("collapsed");
            }
            else {  // Go to PDF element
                self.linkService.navigateTo(e.data.dest);
            }
            return cancel(e);
        });
    }
}

PDFReviewApplication.prototype.setScale = function(scale) {
    var self = this;
    var currentPage = self.currentPage;

    if(scale <= 0.1 || scale >= 10) return;       // Sanity check input
    self.scale = scale;

    // Un-render any existing content
    for(var page = 0; page < self.pdf.numPages; page++) {
        var container = self.pageContainers[page];
        self.unrenderPage(container);
        $(container.reviewLayer).empty();
    }
    // Update page viewport
    self.getPageObj(0).then(function(pageObj) {
        var viewport = pageObj.getViewport(self.scale);
        self.pageContainers[0].viewport = viewport;
        $('.page').css({width: viewport.width, height: viewport.height});

        self.redraw();
        self.linkService.navigateTo("page=" + (currentPage+1));

        // any callback?
        if(self.onscale) self.onscale(self.scale);
        $(window).trigger("pdf-scale");
    });
}

PDFReviewApplication.prototype.zoom = function(zoom) {
    var self = this;
    if(!isNaN(zoom)) self.setScale(parseFloat(zoom));
    else if(zoom == "+") self.setScale(self.scale + self.config.zoomIncrement);
    else if(zoom == "-") self.setScale(self.scale - self.config.zoomIncrement);
    else if(zoom == "page-width" || zoom == "page-fit") {
        self.getPageObj(self.currentPage).then(function(page) {
            var viewport  = page.getViewport(1.0);
            var container = document.getElementById("pdfview");
            if(zoom == "page-width") self.setScale(container.clientWidth/viewport.width);
            if(zoom == "page-fit")   self.setScale(Math.min(container.clientWidth/viewport.width,
                                                            container.clientHeight/viewport.height));
        });
    }
}

PDFReviewApplication.prototype.redraw = function() {
    var self    = this;
    var visible = getVisibleElements(self.pdfView.get(0), self.pageContainers, true);
    if(visible.views.length) {
        var curPage = visible.views[0].view.pageIndex;
        if(curPage != self.currentPage && self.onpagechange) self.onpagechange(curPage, self.pdf.numPages);
        self.currentPage = curPage;
    }

    // First try to render any visible page
    for(var i = 0; i < visible.views.length; i++) {
        var container = visible.views[i].view;
        if(!container.rendered) self.renderPage(container);
    }

    // Then speculatively render any upcoming page (to enable smooth scrolling)
    for(var i = visible.last.view.pageIndex; i < self.pdf.numPages && i < (visible.last.view.pageIndex + self.config.preloadRadius); i++) {
        var container = self.pageContainers[i];
        if(!container.rendered) self.renderPage(container);
    }

    // Then speculatively render any previous page
    for(var i = visible.first.view.pageIndex; i >= 0 && i > (visible.last.view.pageIndex - self.config.preloadRadius); i--) {
        var container = self.pageContainers[i];
        if(!container.rendered) self.renderPage(container);
    }

    // Then remove obsolete pages
    for(var i = 0; i < self.pdf.numPages; i++) {
        if(i < (visible.first.view.pageIndex - self.config.destroyRadius) || i > (visible.last.view.pageIndex + self.config.destroyRadius)) {
            self.unrenderPage(self.pageContainers[i]);
        }
    }
}

PDFReviewApplication.prototype.renderPage = function(container) {
    var self = this;

    if(container.rendered) return;
    container.rendered = true;
    $(container).addClass("loading-animation");

    self.getPageObj(container.pageIndex).then(function(page) {
        var viewport = page.getViewport(self.scale);
        $(container).css({width: viewport.width, height: viewport.height});
        $(container.textLayer).css({width: viewport.width, height: viewport.height});
        container.viewport = viewport;

        // Render SVG
        page.getOperatorList().then(function(opList) {
            var svg = new pdfjsLib.SVGGraphics(page.commonObjs, page.objs);
            return svg.getSVG(opList, viewport);
        }).then(function (svg) {
            svg.setAttribute("class", "the-svg");
            $(container).append(svg);
            $(container).removeClass("loading-animation")
        });

        // New mode: render canvas
        // var ctx = $(container).getContext('2d');
        // page.render({ canvasContext: ctx, viewport: viewport }).then(function(cvs) {
        //     console
        // })

        // Add the text layer
        self.getPageText(container.pageIndex).then(function(pdfText) {
            pdfjsLib.renderTextLayer({
                textContent:    pdfText,
                container:      container.textLayer,
                viewport:       viewport,
                textDivs:       [],
                enhanceTextSelection: false
            });
        });

        // Add review layer
        self.commentService.redraw(container.pageIndex, container);

        // Add annotation layer
        page.getAnnotations({intent: 'display'}).then(function (annotations) {
            var parameters = {
                viewport:       viewport.clone({ dontFlip: true }),
                div:            container.annotationLayer,
                annotations:    annotations,
                page:           page,
                imageResourcesPath: 'img/',
                renderInteractiveForms: true,
                linkService:    self.linkService
            };
            pdfjsLib.AnnotationLayer.render(parameters);
        });
    });
}

PDFReviewApplication.prototype.unrenderPage = function(container) {
    var self = this;
    if(container.rendered) {
        $(container).find(".the-svg").remove();
        $(container.textLayer).empty();
        $(container.annotationLayer).empty();
        container.rendered = false;
    }
}

PDFReviewApplication.prototype.getPageContainer = function(pageId) {
    var self = this;
    if(!self.pdf) return null;
    if(pageId < 0) pageId = 0;
    if(pageId >= self.pdf.numPages) pageId = self.pdf.numPages - 1;
    return self.pageContainers[pageId];
}

PDFReviewApplication.prototype.getPageObj = function(pageId) {
    var self = this;
    var pageContainer = this.getPageContainer(pageId);
    return new Promise(function(resolve) {
        if(pageContainer.page) resolve(pageContainer.page);
        else self.pdf.getPage(pageId + 1).then(function(pageObj) {
            self.pageContainers[pageId].page = pageObj;
            self.pageContainers[pageId].viewport = pageObj.getViewport(self.scale);
            resolve(pageObj);
        });
    });
}

PDFReviewApplication.prototype.getPageText = function(pageId) {
    var self = this;
    var pageContainer = this.getPageContainer(pageId);
    return new Promise(function(resolve) {
        if(pageContainer.pdfText) resolve(pageContainer.pdfText);
        else self.getPageObj(pageId).then(function(pageObj) {
            pageObj.getTextContent().then(function(textContent) {
                self.pageContainers[pageId].pdfText = textContent;
                resolve(textContent);
            });
        });
    });
}

