#!/bin/python

config = {
    "branding":             "PDFReview test instance",
    "url":                  "http://localhost/pdfreview/index.cgi",
    "pdf_path":             "./pdfs/",
    "db_host":              "localhost",
    "db_user":              "webuser",
    "db_passwd":            "password",
    "db_name":              "pdf",
    "ghostscript_path":     "/usr/bin/gs",
    "debug":                True,
    "no_review_msg":        "No reviews in progress. Create one today!",
}

def do_login():
    return ('user', 'user@example.com')
