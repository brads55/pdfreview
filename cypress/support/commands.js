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
    cy.fixture(fileName, 'base64').then(fileContent => {
        cy.get('#drag-to-upload').upload(
            { fileContent, fileName, mimeType: 'application/pdf', encoding:'base64' },
            { subjectType: 'drag-n-drop' },
        );
        cy.url().should('contain', '?review=');
    });
});

Cypress.Commands.add('pdf', (fileName) =>{
    cy.upload_pdf(fileName);
    cy.location().then((loc)=>{
        var parsed = queryString.parse(loc.search);
        delete parsed['new'];
        const newsearch = queryString.stringify(parsed);
        var newurl = 'http://localhost' + loc.pathname + '?' + newsearch;
        cy.log(newurl);
        cy.visit(newurl);
        cy.url().should('contain', '?review=');
    });
});

Cypress.Commands.add("reset_db", ()=>{
    return cy.request('test_reset.cgi').its('body').should('include', 'done');
});


