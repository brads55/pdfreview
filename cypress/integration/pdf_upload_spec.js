

describe('PDF Upload page', ()=>{

    beforeEach(()=>{
        cy.reset_db();
    });

    it('Shows the upload area', ()=>{
        cy.visit('index.cgi');
        cy.get('#drag-to-upload').should('exist');
    });

    it('Allows you to upload PDF files, and redirects to the review page', ()=>{
        // TODO remove this hack as soon as cypress is fixed
        // see: https://github.com/cypress-io/cypress/issues/5717
        // see: CI hack in /pdfreview/index.html
        // cy.visit(''); should really be cy.visit('index.cgi');
        cy.visit('');
        cy.upload_pdf('blank.pdf').then(()=>{
            cy.url().should('include', 'index.cgi?review=');
            cy.get('div#pdfview').should('exist');
        });
    });

    it('Shows all existing PDF reviews', ()=>{
        cy.visit('');
        cy.upload_pdf('blank.pdf').then(()=>{
            cy.visit('');
            cy.contains('blank.pdf').should('exist');
        });
    });

});
