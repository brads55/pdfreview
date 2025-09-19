from typing import Any

from auth import UserInfo

config: dict[str, Any] = {
    "branding": "<company name>",
    "url": "http://path.to",
    "pdf_path": "./pdfs/",
    "db_host": "<sql database>",
    "db_user": "<sql user>",
    "db_passwd": "<sql pwd>",
    "db_name": "<sql db>",
    "ghostscript_path": "/path/to/gs",
    "debug": False,
    # Messages
    "no_review_msg": "No reviews in progress. Create one today!",
    # The following are used for MSAL authentication
    # If an alternative authentication mechanism is used, the following entries can be removed.
    "msal_client_id": "<msal client uuid>",
    "msal_client_credential": "<msal client credential>",
    "msal_tenant": "<msal client tenant>",
    "msal_secret": "<msal client secret>",
}


def is_admin(current_user: UserInfo):
    return True
