
function test_zoom(in_func, out_func){
    cy.contains('Search for the words on this page').should('be.visible');
    cy.get('div.page').then(els => {
        var el = els[0];
        var start_size = el.computedStyleMap().get('width').value;
        out_func();
        cy.get('div.page').then(els => {
            var el = els[0];
            var small_size = el.computedStyleMap().get('width').value;
            in_func();
            in_func();
            cy.get('div.page').then(els => {
                var el = els[0];
                var large_size = el.computedStyleMap().get('width').value;
                cy.wrap(start_size).should('be.greaterThan', small_size);
                cy.wrap(large_size).should('be.greaterThan', start_size);
            });
        });
    });
}

describe('PDF viewer navigation', ()=>{

    beforeEach(()=>{
        cy.reset_db();
    });

    it('Lets you zoom in and out on the PDF', ()=>{
        cy.pdf('search_me.pdf').then(()=>{
            // By clicking the buttons
            test_zoom(()=>{
                cy.get('div#button-zoom-plus').should('be.visible').click();
            },()=>{
                cy.get('div#button-zoom-minus').should('be.visible').click();
            });

            // By doing ctrl+= and ctrl+-
            test_zoom(()=>{
                cy.get('body')
                    .trigger('keydown', { keyCode: 187, key:'=', code:'Equal', ctrlKey:true })
                    .trigger('keyup', { keyCode: 187, key:'=', code:'Equal', ctrlKey:true })
            },()=>{
                cy.get('body')
                    .trigger('keydown', { keyCode: 189, key:'-', code:'Minus', ctrlKey:true })
                    .trigger('keyup', { keyCode: 189, key:'-', code:'Minus', ctrlKey:true })
            });

            // By scrolling with ctrl held
            test_zoom(()=>{
                cy.get('body')
                    .trigger('wheel', { deltaY:-1, ctrlKey:true })
            },()=>{
                cy.get('body')
                    .trigger('wheel', { deltaY:1, ctrlKey:true })
            });
        });
    });

    it('Lets you skip to a specific page number', ()=>{
        cy.pdf('search_me.pdf').then(()=>{
            cy.contains('Search for the words on this page').should('be.visible');
            cy.get('input#page-number').type('3{enter}');
            cy.contains('page 3').should('be.visible');
        });
    });

});
