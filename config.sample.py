from typing import Any

config: dict[str, Any] = {
    "branding": "<company name>",
    "url": "http://path.to/index.cgi",
    "pdf_path": "./pdfs/",
    "db_host": "<sql database>",
    "db_user": "<sql user>",
    "db_passwd": "<sql pwd>",
    "db_name": "<sql db>",
    "ghostscript_path": "/path/to/gs",
    "debug": False,
    # Messages
    "no_review_msg": "No reviews in progress. Create one today!",
    # The following are used for ADAL authentication
    # If an alternative authentication mechanism is used, the following entries can be removed.
    "adal_expires_sec": 15 * 24 * 60 * 60,
    "adal_resource": "<resource eg: https://graph.microsoft.com>",
    "adal_tenant": "<adal tenant uuid>",
    "adal_authority_host": "<adal host eg: https://login.microsoftonline.com>",
    "adal_client_id": "<adal client uuid>",
    "adal_client_secret": "<adal client secret>",
}


def do_login():
    login_name = "<some way of authenticating: user-friendly name>"
    login_email = "<some way of authenticating: unique email>"

    # adal_result = adal_auth.login(conn, config)
    # if adal_result:
    #    login_email = cast(str, adal_result["email"])
    #    login_name = cast(str, adal_result["name"])
    #
    #    return (login_name, login_email)
    #
    # print('{"errorCode": 1, "errorMsg": "Authentication failed"}')
    # sys.exit(0)

    return (login_name, login_email)


def is_admin(login_name: str, login_email: str):
    return True
