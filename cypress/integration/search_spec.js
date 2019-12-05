describe('Search tool', ()=>{

    before(()=>{
        cy.reset_db();
        cy.pdf('search_me.pdf').then(url=>{
            cy.visit(url)
        });
    });

    it('Summons the search box when you click search', ()=>{
        cy.contains('Search for the words on this page.');
        cy.get('div#button-search-toggle').click();
        cy.get('input#search-tool-query').should('be.visible');
        cy.get('div#button-search-toggle').click();
        cy.get('input#search-tool-query').should('not.be.visible');
    });

    it.skip('Summons the search box when you CTRL-F', ()=>{
        cy.contains('Search for the words on this page.');
        cy.get('body').type('{ctrl}f');
        cy.get('input#search-tool-query').should('be.visible');
        cy.get('body').type('{esc}');
        cy.get('input#search-tool-query').should('not.be.visible');
    });

    it('Finds matching texts on multiple pages', ()=>{
        cy.contains('Search for the words on this page.');
        cy.get('body').type('{ctrl}f');
        cy.get('input#search-tool-query').should('be.visible').type('Search for the words{enter}');
        cy.get('div#sidebar-left-search-results').should('contain', '1:').and('contain', '2:');
        cy.get('div#sidebar-left-search-results').children().then(els => {
            cy.wrap(els).should('have.property', 'length', 2);
            cy.wrap(els[0]).click()
            cy.get('div#search-result-0').should('be.visible').should('have.class', 'selected');
            cy.wrap(els[1]).click()
            cy.get('div#search-result-1').should('be.visible').should('have.class', 'selected');
        });
    });

    // This one currently fails because of a slight UX issue :( See issue #12
    // https://github.com/Franchie/pdfreview/issues/12
    it.skip('Lets you jog up and down results using butons and keyboard shortfuts', ()=>{
        cy.get('div#sidebar-left-search-results').children().then(els => {
            cy.wrap(els).should('have.property', 'length', 2);
            cy.wrap(els[0]).click()
            cy.get('div#search-result-0').should('be.visible').should('have.class', 'selected');
            cy.get('div#button-search-next').click()
            cy.get('div#search-result-1').should('be.visible').should('have.class', 'selected');
            cy.get('div#button-search-prev').click()
            cy.get('div#search-result-0').should('be.visible').should('have.class', 'selected');

            cy.get('body').trigger('keydown', { keyCode: 114 })
                .trigger('keyup', { keyCode: 114 })
            cy.get('div#search-result-1').should('be.visible').should('have.class', 'selected');
            cy.get('body')
                .trigger('keydown', { keyCode: 16 })
                .trigger('keydown', { keyCode: 114 })
                .trigger('keyup', { keyCode: 114 })
                .trigger('keyup', { keyCode: 16 })
            cy.get('div#search-result-0').should('be.visible').should('have.class', 'selected');
        });
    });
});


