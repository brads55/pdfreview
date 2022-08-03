

describe('The various sidebars', ()=>{

    beforeEach(()=>{
        cy.reset_db();
    });

    function resize_test(test_desc, div_name, startx, endx, setup_func) {
        it(test_desc, ()=>{
            cy.pdf('internal_links.pdf').then(()=>{
                setup_func();
                cy.get('div#'+div_name).should('be.visible').then(els => {
                    var start_size = els[0].computedStyleMap().get('width').value;
                    cy.get('div#' + div_name + '-resizer')
                        .trigger('mousedown', {x:startx,y:100})
                    cy.get('body')
                        .trigger('mousemove', {x:endx,y:100})
                        .trigger('mouseup', {x:endx,y:100});
                    cy.get('div#' + div_name).then(els => {
                        var new_size = els[0].computedStyleMap().get('width').value;
                        cy.wrap(new_size).should('be.greaterThan', start_size);
                    });
                });
            });
        });
    }

    resize_test('Allows resizing of the outline view', 'sidebar-left', 1, 200, ()=>{
        cy.get('div#button-left-sidebar-toggle').click();
    });
    resize_test('Allows resizing of the comment view', 'sidebar-right', 1, 400, ()=>{});

});
