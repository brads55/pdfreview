

describe('PDF Upload page', ()=>{

    beforeEach(()=>{
        cy.reset_db();
    });

    it('Shows the upload area', ()=>{
        cy.visit('index.cgi');
        cy.get('#drag-to-upload').should('exist');
    });

    it('Allows you to upload PDF files, and redirects to the review page, clipboard modal dialog works', ()=>{
        // TODO remove this hack as soon as cypress is fixed
        // see: https://github.com/cypress-io/cypress/issues/5717
        // see: CI hack in /pdfreview/index.html
        // cy.visit(''); should really be cy.visit('index.cgi');
        cy.visit('');
        cy.upload_pdf('blank.pdf').then(()=>{
            cy.url().should('include', 'index.cgi?review=');
            cy.get('div#pdfview').should('exist');
            cy.contains('The PDF is now ready to be reviewed.').should('be.visible');
            cy.get('div#button-copy-to-clip-link').should('be.visible').click();
            cy.task('getClipboard').should('contain', 'index.cgi?review=');
        });
    });

    it('Shows all existing PDF reviews', ()=>{
        cy.visit('');
        cy.upload_pdf('blank.pdf').then(()=>{
            cy.visit('');
            cy.contains('blank.pdf').should('exist');
        });
    });

    it('Allows you to close and reopen existing reviews', ()=>{
        cy.pdf('blank.pdf').then(()=>{
            cy.visit('');
            cy.contains('Close review').click();
            cy.contains('Your closed reviews:');
            cy.contains('Reopen').click();
            cy.contains('Your active reviews:');
        });
    });

    it('Allows you to delete existing reviews', ()=>{
        cy.pdf('blank.pdf').then(()=>{
            cy.visit('');
            cy.contains('Close review').click();
            cy.contains('Your closed reviews:');
            cy.contains('Delete').click();
            cy.contains('No reviews in progress.');
        });
    });

    it('Presents a password prompt when a pdf is password protected', ()=>{
        cy.pdf('secret.pdf').then(()=>{
            // Check the UI and the owner password and button click to submit
            cy.contains('Please enter a password to join this review.');
            cy.get('input#password-prompt').type('owner');
            cy.contains('Submit').click()
            cy.contains('This is a super secret PDF');
        });
    });

    it.skip('Lets the user press enter to confirm the password on the password prompt', ()=>{
        cy.pdf('secret.pdf').then(()=>{
            // Check the user password and keyboard enter key submit
            cy.get('input#password-prompt').type('user{enter}');
            cy.contains('This is a super secret PDF');
        });
    });

    // Not sure how best to test this, it opens in a new tab or window, and also triggers that bug in cypress
    it.skip('Allows you to download archived PDFs', ()=>{
        cy.pdf('blank.pdf').then(()=>{
            cy.visit('');
            cy.contains('Close review').click();
            cy.contains('Your closed reviews:');
            cy.contains('Archived PDF').click();
            cy.url().should('include', '/pdfs/');
            cy.url().should('include', '.pdf');
        });
    });

    // Same issue as above, but also there is an acutal bug in pdfreview right now, sadly tricky to test it
    // because of the cypress bug and tricky-to-test new tab thing
    it.skip('Allows you to download archived PDFs with passwords', ()=>{
        cy.pdf('secret.pdf').then(()=>{
            cy.visit('');
            cy.contains('Close review').click();
            cy.contains('Your closed reviews:');
            cy.contains('Archived PDF').click();
            cy.url().should('include', '/pdfs/');
            cy.url().should('include', '.pdf');
        });
    });

});
