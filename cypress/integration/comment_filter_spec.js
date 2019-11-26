describe('Comment filter system', ()=>{

    before(()=>{
        cy.reset_db();
        cy.pdf('blank.pdf').then(url=>{
            cy.comment(url, '1', 'Test comment 1', {});
            cy.comment(url, '2', 'Test comment 2', {});
            cy.comment(url, '3', 'Comment test 3', {});
            cy.comment(url, '4', 'Comment test 3', {});
            cy.comment(url, '4r1', 'Reply 1', {replyToId:'4'});
            cy.comment(url, '4r2', 'Reply 2', {replyToId:'4'});
            cy.comment(url, '4r1r1', 'Reply to reply 1', {replyToId:'4r1'});
            cy.visit(url);
        });
    });

    it('shows all comments by default', ()=>{
        cy.get('div#comment-status-msg').should('contain', 'Showing 4 of 4');
    });

    it('allows you to filter comments by text content', ()=>{
        cy.get('div#button-comment-filter').click();
        cy.get('input#comment-filter-text').type('Test comment');
        cy.contains('Filter comments').click();
        cy.get('div#comment-status-msg').should('contain', 'Showing 2 of 4');
        // Test clearing the filter again after
        cy.get('div#button-comment-filter').click();
        cy.contains('Show all comments').click();
        cy.get('div#comment-status-msg').should('contain', 'Showing 4 of 4');
    });

});
