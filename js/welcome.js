/*
 * Javascript functions for the welcome screen.
 * Francois Botman, 2017.
 */

function cancel(e) {
    e.preventDefault();
    e.stopPropagation();
    return false;
}

function fileUpload(file, targetElem, targetMsg)
{
    if(!file.name.toLowerCase().endsWith(".pdf")) {
        targetMsg.html('<SPAN style="color: red;">Document is not a PDF</SPAN><BR/>Please upload a <B>PDF</B> document to create a new review');
        return;
    }
    targetElem.addClass("loading-animation");
    targetMsg.html("Uploading " + file.name + "...");

    var formData = new FormData();
    formData.append("action", 'upload');
    formData.append("filename", file.name);
    formData.append("file", file);
    server.get_data(window.scriptURL, { nocache: true,
                                        postdata: formData,
                                        progress: function(percent) {
                                            if(percent > 0) targetMsg.html("Uploading " + file.name + " (" + percent + "% complete)");
                                        },
                                        complete: function(p) {
        targetElem.removeClass("loading-animation");
        if(p && p.errorCode == 0) {
            // Successfully uploaded. Now let's do something about it.
            window.location.href = '?review=' + p.reviewId + '&new=true';
        }
        else {
            alert("Failed to upload the document." + (p ? "\n"+p.errorMsg : ""));
        }
    }});
}


$( document ).ready(function() {
    var targetElem  = $('#drag-to-upload');
    var targetMsg   = $('#drag-msg');
    var targetInput = $('#click-to-upload');

    window.server = new Server();

    // Is file Drag&Drop supported?
    if(window.FileReader) {
        function dragStart(e) {
            if(!window.dragActive) targetElem.addClass("active");
            window.dragActive = true;
            return cancel(e);
        }
        function dragEnd(e) {
            if(window.dragActive) targetElem.removeClass("active");
            window.dragActive = false;
            return cancel(e);
        }

        $(window).on("drag",      dragStart);
        $(window).on("dragstart", dragStart);
        $(window).on("dragenter", dragStart);
        $(window).on("dragover",  dragStart);
        $(window).on("dragend",   dragEnd);
        $(window).on("dragexit",  dragEnd);
        $(window).on("dragleave", dragEnd);

        $(window).on("drop", function (e) {
            var files = e.originalEvent.dataTransfer.files;
            dragEnd(e);
            fileUpload(files[0], targetElem, targetMsg);
            return cancel(e);
        });

        targetMsg.html('Drag <A HREF="#">or select</A> a PDF document here to create a new review');
    }

    // If dragging is not supported don't tempt the user into dragging a file here
    else {
        targetMsg.html('<A HREF="#">Upload a PDF document</A> to create a new review');
    }

    // Handle File click-upload events
    targetElem.on("click", function(e) {
        if(!window.dragActive) {
            window.dragActive = true;
            cancel(e);
            targetInput.click();
            return false;
        }
        else window.dragActive = false;
    });
    targetInput.on("change", function(e) {
         var files = targetInput.prop("files");
         if(files.length > 0) fileUpload(files[0], targetElem, targetMsg);
    });

    // Get review list:
    var db = new Dexie('pdfreview-reviewlist');
    db.version(1).stores({reviews: "id,closed"});

    function updateReviewList() {
        // Find any reviews
        $('#review-list-none').show();
        db.reviews.filter(function(obj) {return obj.closed == false;}).toArray(function(reviews) {
            var html = '';
            if(reviews.length) {
                $('#review-list-none').hide();
                html += "Your active reviews:<BR/>\n";
                html += '<TABLE class="review-list">\n';
                for(var i = 0; i < reviews.length; i++) {
                    var review = reviews[i];
                    escaped = document.createElement('p');
                    escaped.appendChild(document.createTextNode(review["title"]));
                    html += '\t<TR><TD><A HREF="' + window.scriptURL + '?review=' + review["id"] + '">' + escaped.innerHTML + '</A></TD>';
                    if(review["owner"]) {
                        html += '<TD class="has-border online-only"><A HREF="#" onclick="api(\'' + window.scriptURL + '?review=' + review["id"] + '&api=close-review\');">Close review</A></TD>';
                    } else {
                        html += '<TD></TD>';
                    }
                    html += '</TR>\n';
                }
                html += '</TABLE><BR/><BR/>\n\n';
            }
            $('#review-list-open').html(html);

            db.reviews.filter(function(obj) {return obj.closed == true;}).toArray(function(reviews) {
                var html = '';
                if(reviews.length) {
                    $('#review-list-none').hide();
                    html += "Your closed reviews:<BR/>\n";
                    html += '<TABLE class="review-list">\n';
                    for(var i = 0; i < reviews.length; i++) {
                        var review = reviews[i];
                        html += '\t<TR><TD><A HREF="' + window.scriptURL + '?review=' + review["id"] + '&closed=true">' + review["title"] + '</A></TD>';
                        html += '<TD class="has-border online-only"><A HREF="#" onclick="api(\'?review=' + review["id"] + '&api=pdf-archive\');">Archived PDF</A></TD>';
                        if(review["owner"]) {
                            html += '<TD class="has-border online-only"><A HREF="#" onclick="api(\'' + window.scriptURL + '?review=' + review["id"] + '&api=reopen-review\');">Reopen</A></TD>';
                            html += '<TD class="has-border online-only"><A HREF="#" onclick="if(confirm(\'Really really sure?\')) api(\'' + window.scriptURL + '?review=' + review["id"] + '&api=delete-review\');">Delete</A></TD>';
                        } else {
                            html += '<TD></TD><TD></TD>';
                        }
                        html += '</TR>\n';
                    }
                    html += '</TABLE><BR/><BR/>\n\n';
                }
                $('#review-list-closed').html(html);
            });
        });
    }

    // Fetch new list from server and store for offline use.
    server.get_data(window.scriptURL + "?api=get-review-list", {nocache: true,
                                                                onlineOnly: true,
                                                                complete: function(p) {
        if(p && p.errorCode == 0) {
            db.transaction("rw", "reviews", function() {
                db.reviews.clear();
                db.reviews.bulkPut(p.reviews).then(updateReviewList);
            });
        }
        else {
            // Ideally we'd like to only show the list once. But if we're uploading
            // a lot of offline data this introduces a UI lag that prevents the list being displayed.
            // So let's always display it here, even if that sometimes produces a bizarre flashing in the
            // UI as it is updated again.
            updateReviewList();
        }
    }});
});
