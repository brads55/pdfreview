import 'cypress-file-upload';

function select(el){
    const document = el.ownerDocument;
    const range = document.createRange();
    range.selectNodeContents(el);
    document.getSelection().removeAllRanges(range);
    document.getSelection().addRange(range);
    cy.document().trigger('selectionchange')
}

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
                select(els[0]);
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
                select(els[0]);
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
});

describe('PDF viewer comment sidebar', ()=>{

    before(()=>{
        cy.reset_db();
        cy.pdf('blank.pdf').then(url=>{
            cy.visit(url);
            cy.comment(url, 'point', 'Test comment', {});
        });
    });

    it('shows existing comments', ()=>{
        cy.get('div#comment-container').should('contain', 'Test comment');
    });

});
