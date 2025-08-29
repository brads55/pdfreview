from typing import Any

config: dict[str, Any] = {
    "branding": "PDFReview test instance",
    "url": "http://localhost/pdfreview",
    "pdf_path": "./pdfs/",
    "db_host": "localhost",
    "db_user": "webuser",
    "db_passwd": "password",
    "db_name": "pdf",
    "ghostscript_path": "/usr/bin/gs",
    "debug": True,
    "no_review_msg": "No reviews in progress. Create one today!",
}
