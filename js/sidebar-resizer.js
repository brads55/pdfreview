/*
 * Javascript functions to resize the sidebars.
 * Francois Botman, 2017.
 */

function SidebarResizer(targetElem, leftright, associatedElement) {
    var div = document.createElement("DIV");

    $(div).addClass("resizer");
    document.body.appendChild(div);
    this.hidden            = false;
    this.div               = div;
    this.leftright         = leftright;
    this.targetElem        = targetElem;
    this.associatedElement = associatedElement;
    this._placeBars();
    var self = this;

    $(div).mousedown(function (e) {
        self.active = true;
        e.preventDefault();
        $(div).addClass("active");
        self.divStartX = $(div).offset().left;
        self.startX    = e.pageX;
        $(document).mousemove(function (e) {
            var deltax = e.pageX - self.startX;
            $(div).css("left", (self.divStartX + deltax) + "px");
            return cancel(e);
        });
        return cancel(e);
    });
    $(document).mouseup(function (e) {
        if(!self.active) return;
        $(document).unbind('mousemove');
        $(div).removeClass("active");
        var delta = (leftright == "right") ? (e.pageX - self.startX) : (self.startX - e.pageX);
        self.resize(delta);
        self.active = false;
        return cancel(e);
    });
    $(window).on("resize", function(e) {
        startX = $(targetElem).position().left;
        if(leftright == "right") startX += targetElem.offsetWidth;
        $(div).css("left", startX + "px");
    });
}

SidebarResizer.prototype._placeBars = function() {
    var startX = $(this.targetElem).position().left;
    if(this.leftright == "right") startX += this.targetElem.offsetWidth - 3;
    $(this.div).css("left", startX + "px");
}

SidebarResizer.prototype.resize = function(delta) {
    var percentTotal = 0;
    var self         = this;
    var parentWidth  = this.targetElem.parentElement.offsetWidth;
    $(this.associatedElement).css("width", ((this.associatedElement.offsetWidth - delta) * 100.0 / parentWidth) + "%");
    $(this.targetElem.parentElement).children('div').each(function(index, elem) {
        if(elem != self.targetElem) percentTotal += parseFloat(elem.style.width);
    });
    $(this.targetElem).css("width", (100.0 - percentTotal) + "%");
}

SidebarResizer.prototype.toggle = function() {
    if(!this.hidden) this.hide();
    else this.show();
}

SidebarResizer.prototype.hide = function() {
    if(!this.hidden) {
        this.originalWidth = this.targetElem.offsetWidth;
        this.resize(0 + 1 - this.originalWidth);
        $(this.targetElem).hide();
        $(this.div).hide();
        this.hidden = true;
        $(window).trigger("resize.tool");
    }
}

SidebarResizer.prototype.show = function() {
    if(this.hidden) {
        $(this.div).show();
        $(this.targetElem).show();
        this.resize(this.originalWidth - 1);
        this._placeBars();
        this.hidden = false;
        $(window).trigger("resize.tool");
    }
}
