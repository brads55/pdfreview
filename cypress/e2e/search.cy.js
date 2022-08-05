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

    // realType needs Google Chrome or Electron, skip this test if in firefox
    const ctrl_f_test = ()=>{
        cy.contains('Search for the words on this page.');
        cy.get('body').type('{ctrl}f');
        cy.get('input#search-tool-query').should('be.visible');
        cy.get('input#search-tool-query').realType('{esc}');
        cy.get('input#search-tool-query').should('not.be.visible');
    };
    if (Cypress.browser.name == 'firefox'){
        it.skip('Summons the search box when you CTRL-F', ctrl_f_test);
    }
    else{
        it('Summons the search box when you CTRL-F', ctrl_f_test);
    }

    it('Finds matching texts on multiple pages', ()=>{
        cy.contains('Search for the words on this page.');
        cy.get('div#button-search-toggle').click();
        cy.get('input#search-tool-query').should('be.visible').type('Search for the words{enter}');
        cy.get('div#sidebar-left-search-results').should('contain', '1:').and('contain', '2:');
        cy.get('div#sidebar-left-search-results').children().then(els => {
            cy.wrap(els).should('have.property', 'length', 2);
            cy.wrap(els[0]).click()
            cy.get('div#search-result-0').should('be.visible').should('have.class', 'selected');
            cy.wrap(els[1]).click()
            cy.get('div#search-result-1').should('be.visible').should('have.class', 'selected');
        });
        cy.get('div#button-search-toggle').click();
    });

    // This one currently fails because of a slight UX issue :( See issue #12
    // https://github.com/Franchie/pdfreview/issues/12
    it.skip('Lets you jog up and down results using butons and keyboard shortcuts', ()=>{
        cy.contains('Search for the words on this page.');
        cy.get('div#button-search-toggle').click();
        cy.get('input#search-tool-query').should('be.visible').type('Search for the words{enter}');
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
            // Is this even how you do modifier keys????
            cy.get('body')
                .trigger('keydown', { keyCode: 16 })
                .trigger('keydown', { keyCode: 114 })
                .trigger('keyup', { keyCode: 114 })
                .trigger('keyup', { keyCode: 16 })
            cy.get('div#search-result-0').should('be.visible').should('have.class', 'selected');
        });
        cy.get('div#button-search-toggle').click();
    });

    it('Can be case sensitive', ()=>{
        cy.contains('Search for the words on this page.');
        cy.get('div#button-search-toggle').click();
        cy.get('input#search-tool-query').should('be.visible').type('search{enter}');
        cy.get('div#sidebar-left-search-results').children().then(els => {
            cy.wrap(els).should('have.property', 'length', 2);
        });
        cy.contains('Match case').click();
        cy.get('div#sidebar-left-search-results').then(els =>{
            var el = els[0];
            cy.wrap(el.children).should('have.property', 'length', 0);
        });
        cy.contains('Match case').click();
        cy.get('div#button-search-toggle').click();
    });

    it('Can use a regex', ()=>{
        cy.contains('Search for the words on this page.');
        cy.get('div#button-search-toggle').click();
        cy.get('input#search-tool-query').should('be.visible').type('page (two|3){enter}');
        cy.get('div#sidebar-left-search-results').then(els =>{
            var el = els[0];
            cy.wrap(el.children).should('have.property', 'length', 0);
        });
        cy.contains('Regex').click();
        cy.get('div#sidebar-left-search-results').children().then(els => {
            cy.wrap(els).should('have.property', 'length', 2);
        });
        cy.contains('Regex').click();
        cy.get('div#button-search-toggle').click();
    });

    // https://github.com/Franchie/pdfreview/issues/16
    it.skip('Can find multiple results on one line of text', ()=>{
        cy.contains('Search for the words on this page.');
        cy.get('div#button-search-toggle').click();
        cy.get('input#search-tool-query').should('be.visible').type('a{enter}');
        cy.get('div#sidebar-left-search-results').children().then(els => {
            cy.wrap(els).should('have.property', 'length', 10);
        });
        cy.get('div#button-search-toggle').click();
    });
});

