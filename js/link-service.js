/*
 * Javascript functions to help with ui-related services.
 * Many of these functions are adopted from the pdf.js example code.
 * Francois Botman, 2017.
 */
const LinkTarget = {
      NONE: 0, // Default value.
      SELF: 1,
      BLANK: 2,
      PARENT: 3,
      TOP: 4,
};
const DEFAULT_LINK_REL = "noopener noreferrer nofollow";

function PDFLinkService(pdfApp) {
    var self = this;
    this.pdf     = null;
    this.pdfApp  = pdfApp;
    this.page    = 0;
    this._cachedEntries = {};
    this._numCachedEntries = 0;
    this.nextHistorySilent = false;
    this.config = {
        targetX: 0,
        targetY: 100
    };
    $(window).on("popstate.linkService", function(e) {
        if(e.originalEvent.state) self.navigateTo(e.originalEvent.state, true);
        else if(e.originalEvent.target.location.hash) self.navigateTo(e.originalEvent.target.location.hash.replace("#",""), true);
        return cancel(e);
    });
}

PDFLinkService.prototype.setDocument = function(pdf) {
    this.pdf = pdf;
}

PDFLinkService.prototype.internalLinkUrl = function(dest) {
    return '#' + dest;
}

/**
 * Adds various attributes (href, title, target, rel) to hyperlinks.
 * @param {HTMLAnchorElement} link - The link element.
 * @param {ExternalLinkParameters} params
 */
PDFLinkService.prototype.addLinkAttributes = function(link, url, target, rel, enabled = true) {
    if (!url || typeof url !== "string") {
        throw new Error('A valid "url" parameter must provided.');
    }

    if (enabled) {
        link.href = link.title = url;
    } else {
        link.href = "";
        link.title = `Disabled: ${url}`;
        link.onclick = () => {
            return false;
        };
    }

    let targetStr = ""; // LinkTarget.NONE
    switch (target) {
        case LinkTarget.NONE:
            break;
        case LinkTarget.SELF:
            targetStr = "_self";
            break;
        case LinkTarget.BLANK:
            targetStr = "_blank";
            break;
        case LinkTarget.PARENT:
            targetStr = "_parent";
            break;
        case LinkTarget.TOP:
            targetStr = "_top";
            break;
    }
    link.target = targetStr;

    link.rel = typeof rel === "string" ? rel : DEFAULT_LINK_REL;
}

PDFLinkService.prototype.getDestinationHash = function(dest) {
    var name = "";
    if(typeof dest === 'string')   name = dest;
    else if(dest instanceof Array) {
        if(dest.length == 5 && dest[4]) name = "comment=" + escape(dest[4]);
        else                            name = "_ref" + escape(this._numCachedEntries++);
    }
    for(var i in this._cachedEntries) if(this._cachedEntries[i] === dest) return this.internalLinkUrl(i);
    this._cachedEntries[name] = dest;
    return this.internalLinkUrl(name);
}

PDFLinkService.prototype.goToDestination = function(dest) {
    this.navigateTo(dest, false);
}

PDFLinkService.prototype.navigateTo = function(dest, doNotAddHistory) {
    var self = this;
    if(self.nextHistorySilent) {
        doNotAddHistory = true;
        self.nextHistorySilent = false;
    }

    // Navigate to somewhere unspecified -- default to top.
    if(!dest) $('#pdfview').scrollTop(0).scrollLeft(0);

    // Navigate to somewhere we should know -- search cached records
    else if(typeof dest === 'string') {
        // We've seen this before
        if(dest in self._cachedEntries && self._cachedEntries[dest] instanceof Array) return self.navigateTo(self._cachedEntries[dest]);
        // Navigate to page
        else if(dest.match("page=")) {
            pageId = parseInt(dest.replace("page=","")) - 1
            if(pageId < 0) pageId = 0;
            if(pageId >= self.pdf.numPages) pageId = self.pdf.numPages - 1;
            if(isNaN(pageId)) return;
            var container = self.pdfApp.getPageContainer(pageId);
            $('#pdfview').scrollTop(container.offsetTop - $('#pdfview')[0].getBoundingClientRect().top - 5);
            if(window.history && !doNotAddHistory) history.pushState(dest, "Page " + (pageId + 1), self.getDestinationHash(dest));
        }
        // Comment
        else if(dest.match("comment=")) {
            commentId = dest.replace("comment=","")
            s = $("#review-comment-" + commentId)
            self.nextHistorySilent = true
            if(s) s.click()
        }
        // Named destination
        else {
            self.pdf.getDestination(dest).then(function (destArr) {
                if(!destArr) {
                    console.log("Unknown navigation destination " + dest, self._cachedEntries);
                    return;
                }
                self._cachedEntries[dest] = destArr;
                self.navigateTo(destArr);
            });
        }
    }

    // Navigate to specified location
    else if(dest instanceof Array) {
        function goToPageIndex(pageId, x, y) {
            var container = self.pdfApp.getPageContainer(pageId);
            self.pdfApp.getPageObj(pageId).then(function(page) {
                var viewport = page.getViewport({scale: self.pdfApp.scale});
                var vprect   = viewport.convertToViewportPoint(x, y);
                var rect     = {left: Math.max(vprect[0] - container.offsetLeft - self.config.targetX, 0), top: Math.max(vprect[1] + container.offsetTop - self.config.targetY, 0)};

                $('#pdfview').scrollTop(rect.top).scrollLeft(rect.left);
                if(window.history && !doNotAddHistory) history.pushState(dest, "Page " + (pageId + 1), self.getDestinationHash(dest));
                if(dest.length == 5 && dest[4]) {
                    s = $("#review-comment-" + dest[4])
                    if(s) s.trigger("commentSelect");
                }
                self.pdfApp.redraw();
            });
        }
        if(typeof dest[0] == "string" && dest[0] == "direct") {
            return goToPageIndex(dest[1], dest[2], dest[3]);
        }
        else {
            self.pdf.getPageIndex(dest[0]).then(function(pageId) {
                return goToPageIndex(pageId, dest[2], dest[3]);
            });
        }
    }
}

