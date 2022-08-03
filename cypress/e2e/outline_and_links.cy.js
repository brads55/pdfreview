

describe('PDF outline view and internal links', ()=>{

    beforeEach(()=>{
        cy.reset_db();
    });

    it('Shows all bookmarks in a PDF and lets you click them to jump to them', ()=>{
        cy.pdf('internal_links.pdf').then(()=>{
            cy.get('div#sidebar-left-bookmarks').children().then(els => {
                cy.wrap(els).should('have.property', 'length', 3);
            });
            // Try skippiing to chapter 3
            cy.get('div#sidebar-left-bookmarks').contains('Three').click();
            cy.contains('Chapter 3').should('be.visible');
        });
    });

    it('Allows internal links to jump to parts of the PDF', ()=>{
        cy.pdf('internal_links.pdf').then(()=>{
            cy.get('a.internalLink[href="#chapter.3"]').click();
            cy.contains('Chapter 3').should('be.visible');
        });
    });
});
