

describe('The various sidebars', ()=>{

    beforeEach(()=>{
        cy.reset_db();
    });

    function resize_test(test_desc, div_name, startx, endx) {
        it(test_desc, ()=>{
            cy.pdf('internal_links.pdf').then(()=>{
                cy.get('div#'+div_name).should('be.visible').then(els => {
                    var start_size = els[0].scrollWidth;
                    cy.get('div#' + div_name + '-resizer')
                        .trigger('mousedown', {x:startx,y:100})
                    cy.get('body')
                        .trigger('mousemove', {x:endx,y:100})
                        .trigger('mouseup', {x:endx,y:100});
                    cy.get('div#' + div_name).then(els => {
                        var new_size = els[0].scrollWidth;
                        cy.wrap(new_size).should('be.greaterThan', start_size);
                    });
                });
            });
        });
    }

    resize_test('Allows resizing of the outline view', 'sidebar-left', 1, 200);
    resize_test('Allows resizing of the comment view', 'sidebar-right', 1, 400);

});
