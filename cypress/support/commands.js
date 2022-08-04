// ***********************************************
// This example commands.js shows you how to
// create various custom commands and overwrite
// existing commands.
//
// For more comprehensive examples of custom
// commands please read more here:
// https://on.cypress.io/custom-commands
// ***********************************************
//
//
// -- This is a parent command --
// Cypress.Commands.add("login", (email, password) => { ... })
//
//
// -- This is a child command --
// Cypress.Commands.add("drag", { prevSubject: 'element'}, (subject, options) => { ... })
//
//
// -- This is a dual command --
// Cypress.Commands.add("dismiss", { prevSubject: 'optional'}, (subject, options) => { ... })
//
//
// -- This will overwrite an existing command --
// Cypress.Commands.overwrite("visit", (originalFn, url, options) => { ... })

import 'cypress-file-upload';
const queryString = require('query-string');


Cypress.Commands.add('upload_pdf', (fileName) => {
    cy.visit('');
    cy.get('#drag-to-upload').selectFile('cypress/fixtures/' + fileName, {action: 'drag-drop'});
    cy.url().should('contain', '?review=');
});

var fitpage = () =>{
    cy.get('#pdfview').should('be.visible');
    cy.get('#button-zoom-select').should('be.visible');
    cy.get('#button-zoom-select').select('Page Fit');
}

Cypress.Commands.add('fitpage', fitpage);

Cypress.Commands.add('pdf', (fileName, skipautosize) =>{
    cy.upload_pdf(fileName);
    cy.location().then((loc)=>{
        var parsed = queryString.parse(loc.search);
        delete parsed['new'];
        const newsearch = queryString.stringify(parsed);
        var newurl = 'http://localhost' + loc.pathname + '?' + newsearch;
        cy.log(newurl);
        cy.visit(newurl);
        if (!skipautosize){
            fitpage();
        }
        cy.wait(200); // for good luck :)
        cy.url().should('contain', '?review=')
    });
});

Cypress.Commands.add("reset_db", ()=>{
    return cy.request('test_reset.cgi').its('body').should('include', 'done');
});


Cypress.Commands.add("comment", (url, cid, text, params) =>{
    var parsed = queryString.parse(url);
    var p_url = new URL(url)
    cy.log(p_url);
    var form = {
        'api':'add-comment'
        ,'review': p_url.searchParams.get('review')
        ,'comment': JSON.stringify({
            'msg': text
            ,'id': cid
            ,'rects': [{'tl':[50,50]}]
            ,'pageId':0
            ,'type':'comment'
            , ...params})
    };
    cy.request({method:'POST', url:'/index.cgi', form:true, body:form}).then(resp=>{
        cy.wrap(resp.body).should('have.property', 'errorCode', 0);
    });
});

Cypress.Commands.add("select_el_text", el=>{
    const document = el.ownerDocument;
    const range = document.createRange();
    range.selectNodeContents(el);
    document.getSelection().removeAllRanges(range);
    document.getSelection().addRange(range);
    cy.document().trigger('selectionchange');
});
