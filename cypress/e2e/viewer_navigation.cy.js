
function test_zoom(in_func, out_func){
    cy.contains('Search for the words on this page').should('be.visible');
    cy.get('div.page').then(els => {
        var el = els[0];
        var start_size = el.scrollWidth;
        out_func();
        cy.wait(100);
        cy.contains('Search for the words on this page').should('be.visible');
        cy.get('div.page').invoke('css', 'width').should('not.be', start_size);
        cy.get('div.page').then(els => {
            var el = els[0];
            var small_size = el.scrollWidth;
            in_func();
            cy.wait(100);
            cy.contains('Search for the words on this page').should('be.visible');
            in_func();
            cy.wait(100);
            cy.contains('Search for the words on this page').should('be.visible');
            cy.get('div.page').invoke('css', 'width').should('not.be', small_size);
            cy.get('div.page').invoke('css', 'width').should('not.be', start_size);
            cy.get('div.page').then(els => {
                var el = els[0];
                var large_size = el.scrollWidth;
                cy.wrap(start_size).should('be.greaterThan', small_size);
                cy.wrap(large_size).should('be.greaterThan', start_size);
                out_func();
                cy.wait(100);
                cy.get('div.page').invoke('css', 'width').should('not.be', large_size);
                cy.contains('Search for the words on this page').should('be.visible');
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

            // By doing ctrl+= and ctrl+- (On MacOS, you need to use the CMD key instead of ctrl, called metaKey in JS)
            var ctrlKey = true;
            var metaKey = false;
            if (Cypress.platform == 'darwin'){
                ctrlKey = false;
                metaKey = true;
            }
            test_zoom(()=>{
                cy.get('body')
                    .trigger('keydown', { keyCode: 187, key:'=', code:'Equal', ctrlKey, metaKey })
                    .trigger('keyup', { keyCode: 187, key:'=', code:'Equal', ctrlKey, metaKey })
            },()=>{
                cy.get('body')
                    .trigger('keydown', { keyCode: 189, key:'-', code:'Minus', ctrlKey, metaKey })
                    .trigger('keyup', { keyCode: 189, key:'-', code:'Minus', ctrlKey, metaKey })
            });

            // By scrolling with ctrl held (For some reason this one works fine on MacOS?)
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
            cy.wait(100);
            cy.contains('page 3').should('be.visible');
        });
    });

});
