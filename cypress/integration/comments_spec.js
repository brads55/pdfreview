import 'cypress-file-upload';

describe('PDF viewer comment buttons', ()=>{

    before(()=>{
        cy.reset_db();
        cy.pdf('comment_types.pdf').then(url=>{
            cy.visit(url)
        });
    });

    it('lets you add highlight style comments', ()=>{
        cy.contains('Comment on me').then(els=>{
            cy.get('#button-mode-highlight').click().then(()=>{
                cy.get('div.page.highlight-tool').trigger('mousedown', {which:1});
                cy.select_el_text(els[0]);
                cy.get('div.page.highlight-tool').trigger('mouseup', {which:1});
                cy.contains('Please enter an associated comment');
                cy.get('textarea#comment-msg').type('Comment 1 line 1{enter}Comment 1 line 2{ctrl}{enter}');
                cy.get('div#comment-container').should('contain', 'Comment 1 line 1').should('contain','Comment 1 line 2');
            });
        });
    });

    it('lets you add delete style comments', ()=>{
        cy.contains('Delete me').then(els=>{
            cy.get('#button-mode-strike').click().then(()=>{
                cy.get('div.page.strike-tool').trigger('mousedown', {which:1});
                cy.select_el_text(els[0]);
                cy.get('div.page.strike-tool').trigger('mouseup', {which:1});
                cy.contains('Please enter an associated comment');
                cy.get('textarea#comment-msg').type('Comment 2 line 1{enter}Comment 2 line 2');
                cy.get('div#dialog-comment').contains('Submit').click();
                cy.get('div#comment-container').should('contain', 'Comment 2 line 1').should('contain','Comment 2 line 2');
            });
        });
    });

    it('lets you add rectangle style comments', ()=>{
        cy.contains('Draw a box around me').then(els=>{
            cy.get('#button-mode-rectangle').click().then(()=>{
                const r = els[0].getBoundingClientRect();
                cy.get('div.page.rectangle-tool').then(els=>{
                    const page_r = els[0].getBoundingClientRect();
                    cy.get('div.page.rectangle-tool').trigger('mousedown', - page_r.left + r.left, - page_r.top + r.top, {which:1});
                    cy.get('div.page.rectangle-tool').trigger('mouseup', - page_r.left + r.left + r.width, - page_r.top + r.top + r.height, {which:1});
                    cy.contains('Please enter an associated comment');
                    cy.get('textarea#comment-msg').type('Comment 3');
                    cy.get('div#dialog-comment').contains('Submit').click();
                    cy.get('div#comment-container').should('contain', 'Comment 3');
                });
            });
        });
    });

    it('lets you add point style comments', ()=>{
        cy.contains('Leave a point comment next to me').then(els=>{
            cy.get('#button-mode-comment').click().then(()=>{
                const r = els[0].getBoundingClientRect();
                cy.get('div.page.comment-tool').then(els=>{
                    const page_r = els[0].getBoundingClientRect();
                    var x = - page_r.left + r.left + r.width + 30;
                    var y = - page_r.top + r.top;
                    cy.get('div.page.comment-tool').trigger('click', x, y, {which:1});
                    cy.contains('Please enter an associated comment');
                    cy.get('textarea#comment-msg').type('Comment 4');
                    cy.get('div#dialog-comment').contains('Submit').click();
                    cy.get('div#comment-container').should('contain', 'Comment 4');
                });
            });
        });
    });

    it('lets you add comments with unicode characters', ()=>{
        cy.contains('Leave a point comment next to me').then(els=>{
            cy.get('#button-mode-comment').click().then(()=>{
                const r = els[0].getBoundingClientRect();
                cy.get('div.page.comment-tool').then(els=>{
                    const page_r = els[0].getBoundingClientRect();
                    var x = - page_r.left + r.left + r.width + 90;
                    var y = - page_r.top + r.top;
                    cy.get('div.page.comment-tool').trigger('click', x, y, {which:1});
                    cy.contains('Please enter an associated comment');
                    cy.get('textarea#comment-msg').type('我们可以用UTF-8！棒棒达');
                    cy.get('div#dialog-comment').contains('Submit').click();
                    cy.get('div#comment-container').should('contain', '我们可以用UTF-8！棒棒达');
                });
            });
        });
    });
});

describe('PDF viewer comment sidebar', ()=>{

    before(()=>{
        cy.reset_db();
        cy.pdf('blank.pdf').then(url=>{
            cy.comment(url, 'comment1', 'Test comment', {});
            cy.comment(url, 'deleteme', 'A comment to be deleted', {});
            cy.comment(url, 'accept', 'Accept me', {});
            cy.visit(url);
        });
    });

    it('shows existing comments', ()=>{
        cy.get('div#comment-container')
            .should('contain', 'Test comment')
            .should('contain', 'A comment to be deleted')
            .should('contain', 'Accept me');
    });

    it('allows you to reply to a comment', ()=>{
        // TODO why do I need to click this twice in chrome but not in electron?
        cy.get('div#comment-container').contains('Test comment').click();
        cy.get('div#comment-container').contains('Test comment').click();
        cy.get('div#review-comment-comment1').contains('Reply').click();
        cy.contains('Please enter your response to that comment');
        cy.get('textarea#comment-msg').type('Reply to initial comment');
        cy.get('div#dialog-comment').contains('Submit').click();
        cy.get('div#comment-container').should('contain', 'Reply to initial comment');
    });

    it('allows you to update a comment', ()=>{
        cy.get('div#comment-container').contains('Test comment').click();
        cy.get('div#review-comment-comment1').contains('Update').click();
        cy.contains('Please update your message below');
        cy.get('textarea#comment-msg').type('New text, never seen before');
        cy.get('div#dialog-comment').contains('Submit').click();
        cy.get('div#comment-container').should('contain', 'New text, never seen before');
    });

    it('allows you to delete a comment', ()=>{
        // Let's click on no, make sure the comment stays there
        cy.get('div#comment-container').contains('A comment to be deleted').click();
        cy.get('div#review-comment-deleteme').contains('Delete').click();
        cy.contains('This will delete the selected comment');
        cy.get('div#dialog-confirm').contains('No').click();
        cy.get('div#comment-container').should('contain', 'A comment to be deleted');
        // Now lets actually delete it and make sure it does go
        cy.get('div#comment-container').contains('A comment to be deleted').click();
        cy.get('div#review-comment-deleteme').contains('Delete').click();
        cy.get('div#dialog-confirm').contains('Yes').click();
        cy.get('div#comment-container').should('not.contain', 'A comment to be deleted');
    });

    it('allows you to set a status on a comment', ()=>{
        cy.get('div#comment-container').contains('Accept me').click();
        cy.get('div#review-comment-accept').contains('Status').click();
        cy.get('select.select-status').select('Accepted');
        cy.get('div#review-comment-accept').should('contain', 'Accepted');
    });

    it('scales text when the text scale buttons are clicked', ()=>{
        cy.get('div#comment-container').contains('Accept me').then(els => {
            var el = els[0];
            var start_size = el.computedStyleMap().get('font-size').value;
            cy.get('div#button-comment-text-smaller').click();
            cy.get('div#comment-container').contains('Accept me').then(els => {
                var el = els[0];
                var small_size = el.computedStyleMap().get('font-size').value;
                cy.get('div#button-comment-text-larger').click().click();
                cy.get('div#comment-container').contains('Accept me').then(els => {
                    var el = els[0];
                    var large_size = el.computedStyleMap().get('font-size').value;
                    cy.wrap(start_size).should('be.greaterThan', small_size);
                    cy.wrap(large_size).should('be.greaterThan', start_size);
                });
            });
        });
    });
});
