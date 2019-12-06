/*
 * Javascript functions for the main review screen.
 * Francois Botman, 2017.
 */

function showUILink(url, helperTxt) {
    $('#dialog-ui-link pre').html('<A HREF="' + url + '" target="_blank">' + url + '</A>');
    $("#ui-link-text").html(helperTxt || "")
    if(document.execCommand) {
        $('#button-copy-to-clip-link').on('click', function() {
            var txt = document.createElement("input");
            document.body.appendChild(txt);
            txt.value = url;
            txt.select();
            document.execCommand("copy");
            document.body.removeChild(txt);
        });
    }
    else $('#button-copy-to-clip-link').hide();
    new ModalDialog("dialog-ui-link");
}

function reportError(msg) {
    $('#error-report-details').val(msg || "");
    new ModalDialog("dialog-report-error", function(dialog, button) {
        var details = $('#error-report-details').val();
        var msg     = $('#error-report-msg').val();
        if($(button).data("button") == "submit") {
            var formData = {
                "api":      "report-error",
                "details":  details,
                "msg":      msg,
                "review":   window.reviewId};
            server.get_data(window.scriptURL, { nocache: true, formdata: formData });
        }
    });
}


$( document ).ready(function() {

    window.reviewClosed = $.urlParam("closed");
    window.server = new Server();

    // Setup UI elements
    $('.button').each(function(index, e) {      // Button icons
        if($(e).data("icon")) $(e).css("background-image", "url(" + $(e).data("icon") + ")");
    });
    window.sidebarLeft  = new SidebarResizer($("#sidebar-left")[0],  "right", $('#main-content')[0]);
    window.sidebarRight = new SidebarResizer($("#sidebar-right")[0], "left",  $('#main-content')[0]);
    $("#button-left-sidebar-toggle").on("click", function(e) {
        window.sidebarLeft.toggle();
        $("#button-left-sidebar-toggle").toggleClass("active");
    });
    $("#button-right-sidebar-toggle").on("click", function(e) {
        window.sidebarRight.toggle();
        $("#button-right-sidebar-toggle").toggleClass("active");
    });
    window.sidebarLeft.hide();
    $('#button-comment-text-smaller').on("click", function() {
        var commentContainer = $('#comment-container');
        commentContainer.css('font-size', (parseInt(commentContainer.css('font-size'))-2) + "px")
    });
    $('#button-comment-text-larger').on("click", function() {
        var commentContainer = $('#comment-container');
        commentContainer.css('font-size', (parseInt(commentContainer.css('font-size'))+2) + "px")
    });
    window.onerror = function(messageOrEvent, source, lineno, colno, error) {
        reportError(source + ':' + lineno + ':' + colno +': ' + error + '\n' + messageOrEvent);
        return false;
    };


    // Load main PDF Review application
    window.PDFReviewApp = new PDFReviewApplication(pdfURL);
    window.PDFReviewApp.loadPDF().then(function() {
        window.mouseTools = new MouseTools(window.PDFReviewApp);
        window.mouseTools.selectTool();
        new SearchToolUI(window.PDFReviewApp);
        if(window.reviewClosed) {
            new ModalDialog("dialog-closed-review");
            $('#button-mode-highlight').hide();
            $('#button-mode-rectangle').hide();
            $('#button-mode-strike').hide();
            $('#button-mode-comment').hide();
        }
        if($.urlParam("new")) showUILink(window.scriptURL + "?review=" + reviewId, "The PDF is now ready to be reviewed.<BR/><BR/>Please share the following link to potential reviewers:");
        $("#page-number").on("keydown.page-select", function(e) {
            if (e.which == 13) {        // ENTER
                window.PDFReviewApp.linkService.navigateTo("page=" + $(e.target).val());
                return cancel(e);
            }
        }).on("click.page-select", function(e) {
            e.target.select();
            return cancel(e);
        });
        $('#button-zoom-select').on("change", function() {window.PDFReviewApp.zoom(this.value);});
        $('#button-zoom-plus').on( "click", function() {window.PDFReviewApp.zoom("+");});
        $('#button-zoom-minus').on("click", function() {window.PDFReviewApp.zoom("-");});

        // Mousewheel events have recently been made "passive" by default, which means that
        // it is not possible to prevent default browser behaviours from taking place. This
        // workaround forces these events to be "active" (should work in all modern browsers).
        jQuery.event.special.wheel = {
            setup: function( _, ns, handle ) {
                this.addEventListener("wheel", handle, { passive: false });
            }
        };
        jQuery.event.special.mousewheel = jQuery.event.special.wheel;
        $(window).on('mousewheel wheel', function(e) {
            if(e.ctrlKey || e.metaKey) {
                window.PDFReviewApp.zoom(e.originalEvent.deltaY > 0 ? "-" : "+");
                return cancel(e);
            }
        });
        $(window).on("keydown.zoom", function(e)  {
            if((e.which == 107 || e.which == 187) && (e.ctrlKey || e.metaKey)) {   // + and =
                window.PDFReviewApp.zoom("+");
                return cancel(e);
            }
            if((e.which == 109 || e.which == 189) && (e.ctrlKey || e.metaKey)) {   // - and _
                window.PDFReviewApp.zoom("-");
                return cancel(e);
            }
        });
        window.PDFReviewApp.onscale = function(scale) {
            $('#button-zoom-select-custom').get(0).value = scale;
            $('#button-zoom-select').val(scale);
        }
        window.PDFReviewApp.onpagechange = function(pageId, maxPages) {
            $("#num-pages").text(maxPages);
            $("#page-number").val(pageId + 1);
        }
        var show_ui_tool = false;
        $('#button-link-options').on("click", function(e) {
            if(!show_ui_tool) {
                show_ui_tool = new ModalTool('ui-logo-tool', $(this), function(e) {show_ui_tool = false;});
            }
            else {
                show_ui_tool.close();
                show_ui_tool = false;
            }
        });

        // Enable download of archive copy of review PDF
        function showPDFdownload(password) {
            $('#archive-pdf-download').text("Exporting...").addClass("loading-animation");
            new ModalDialog("dialog-download");
            var formData = {"api": 'pdf-archive', "review": window.reviewId};
            if(password != undefined) formData.append("password", password);
            server.get_data(window.scriptURL, { nocache: true, formdata: formData, onlineOnly: true, complete: function(p) {
                if(p && p.errorCode == 0) {
                    $('#archive-pdf-download').text("Ready.").addClass("ready").removeClass("loading-animation").on("click", function(e) {
                        window.open(p.url);
                    });
                }
                else {
                    $('#archive-pdf-download').text("Failed to download.\n" + (p ? p.errorMsg : "")).addClass("failed").removeClass("loading-animation");
                    if(window.console && p && p.debug) console.error("Debug: reason for failure: ", p.debug);
                }
            }});
        }
        $('#ui-logo-download').on("click", function(e) {
            if(window.PDFReviewApp.isPasswordProtected) {
                $('#password-reason').html('Your password is temporarily required to produce the exported PDF.')
                new ModalDialog("dialog-password", function(dialog, button) {
                    showPDFdownload($('#password-prompt').val());
                });
            }
            else showPDFdownload();
        });
    });
});
