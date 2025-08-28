#!bin/python

# from adal import AuthenticationContext

# auth_context = AuthenticationContext("https://login.microsoftonline.com/contoso.onmicrosoft.com")


import cgi
import cgitb
import json
import os
import sys
import time
import uuid
from typing import Any, cast

import adal
import requests
from sqlalchemy import Connection, sql

from common import print_file

TOKEN_NAME = "adal-token"
REFRESH_TOKEN = "adal-refresh-token"
UUID_TOKEN = "adal-auth-session"
URI_TOKEN = "app-uri-context"


def login(conn: Connection, config: dict[str, Any]):
    try:
        form = cgi.FieldStorage()
        code = cast(str, form.getvalue("code"))
        err = cast(str, form.getvalue("error"))
        errmsg = cast(str, form.getvalue("error_description"))

        config["adal_AUTHORITY_URL"] = config["adal_authority_host"] + "/" + config["adal_tenant"]
        config["adal_RESOURCE"] = "https://graph.microsoft.com"
        config["adal_session_state_timeout_sec"] = 5 * 60 * 60

        if config["debug"]:
            cgitb.enable()

        #
        # Bearer token login
        #
        if "HTTP_AUTHORIZATION" in os.environ:
            bearer = os.environ["HTTP_AUTHORIZATION"]
            user_key = bearer.split(" ", 1)[1]
            # Either this is already in the database, just look it up
            result = db_get_user(conn, user_key)
            if result and len(result) == 2:
                (name, email) = result
                return {"name": name, "email": email.lower()}

            # ....Or it's not, authenticate with microsoft.
            headers = {"Content-Type": "application/json", "Authorization": bearer}
            endpoint = "https://graph.microsoft.com/v1.0/me/"
            response = requests.get(endpoint, headers=headers, timeout=60)
            if response.status_code == 200:
                json_data = json.loads(response.text)
                username = json_data["displayName"]
                useremail = json_data["mail"]
                db_add_user(conn, config, user_key, username, useremail)
                return {"name": username, "email": useremail.lower()}
            # (or keep going if that failed...)

        #
        # If the user has a valid token, validate that now
        #
        cookie = get_cookie(TOKEN_NAME)
        if cookie:
            result = db_get_user(conn, cookie)
            if result and len(result) == 2:
                (name, email) = result
                return {"name": name, "email": email.lower()}
            # Otherwise, the key was not found in the database, move on to other forms of authentication

        #
        # Otherwise, are we returning from an authentication interaction?
        #
        if code:
            if err:
                auth_error(err + ": " + errmsg, config)

            # Disabling state checks -- for some reason this does not play well with offline storage and is causing more problems than it's worth.
            # state_ref = get_cookie(UUID_TOKEN)
            # if (state_ref != state):
            #     auth_error("The session states for ADAL authentication do not match, possible CSI breach. Expected {}, got {}".format(state_ref, state), config)
            token = get_token(code, config)

            headers = {"Content-Type": "application/json", "Authorization": "Bearer {0}".format(token["accessToken"])}
            endpoint = "https://graph.microsoft.com/v1.0/me/"
            response = requests.get(endpoint, headers=headers, timeout=60)

            if response.status_code == 200:
                json_data = json.loads(response.text)
                username = json_data["displayName"]
                useremail = json_data["mail"]
                user_key = uuid.uuid1()

                db_add_user(conn, config, str(user_key), username, useremail)
                uri_context = get_cookie(URI_TOKEN)
                url = config["url"]
                if uri_context:
                    url += uri_context
                print("Status: 307 Redirect")
                print("Location: " + url)
                set_cookie(TOKEN_NAME, str(user_key), config["adal_expires_sec"], "Lax")
                set_cookie(REFRESH_TOKEN, token["refreshToken"], config["adal_session_state_timeout_sec"], "Lax")
                delete_cookie(URI_TOKEN)
                delete_cookie(UUID_TOKEN)
                print("\n")

            else:
                auth_error(
                    f"ADAL endpoint request resulted in a {response.status_code} error ({response.text})",
                    config,
                )
            sys.exit(0)

        #
        # Otherwise, redirect to authentication interface
        #
        redirect_to_portal(config)
        sys.exit(0)

    except adal.AdalError as e:
        auth_error("Adal exception error: " + str(e), config)


def auth_error(msg: str, config: dict[str, Any]):
    print("Content-type: text/html\n")
    print_file("./auth_error.html.template", [[r"%ERROR_MESSAGE%", msg]], config)
    sys.exit(0)


def db_add_user(conn: Connection, config: dict[str, Any], user_key: str, username: str, useremail: str):
    conn.execute(
        sql.text("INSERT INTO adal_auth (authkey, name, email, expire) VALUES (:key, :name, :email, :expire)"),
        {
            "key": user_key,
            "name": username,
            "email": useremail,
            "expire": int(time.time() + config["adal_expires_sec"]),
        },
    )
    conn.commit()


def db_get_user(conn: Connection, user_key: str):
    conn.execute(sql.text("DELETE FROM adal_auth WHERE expire<:time"), {"time": int(time.time())})
    conn.commit()

    # Find user in table
    return conn.execute(sql.text("SELECT name, email from adal_auth WHERE authkey=:key"), {"key": user_key}).fetchone()


def get_cookie(name: str):
    if "HTTP_COOKIE" in os.environ:
        for cookie in map(str.strip, str.split(os.environ["HTTP_COOKIE"], ";")):
            (key, value) = str.split(cookie, "=", 1)
            if key == name:
                return value
    return None


def set_cookie(name: str, value: str, expires_seconds: int, policy: str = "Strict"):
    """This should come after a Content-type response"""
    print(f"Set-Cookie: {name}={value}; SameSite={policy}; Max-age={expires_seconds};")


def delete_cookie(name: str):
    """This should come after a Content-type response"""
    print(f"Set-Cookie: {name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT;")


def redirect_to_portal(config: dict[str, Any]):
    session_state = uuid.uuid1()
    redirect_url = (
        "https://login.microsoftonline.com/{}/oauth2/authorize?"
        + "response_type=code&client_id={}&redirect_uri={}&state={}&resource={}"
    ).format(config["adal_tenant"], config["adal_client_id"], config["url"], session_state, config["adal_RESOURCE"])
    print("Status: 307 Redirect")
    print("Location: " + redirect_url)
    if "?" in os.environ["REQUEST_URI"]:
        set_cookie(
            URI_TOKEN, "?" + os.environ["REQUEST_URI"].split("?")[-1], config["adal_session_state_timeout_sec"], "Lax"
        )
    else:
        set_cookie(URI_TOKEN, "", config["adal_session_state_timeout_sec"], "Lax")
    set_cookie(UUID_TOKEN, str(session_state), config["adal_session_state_timeout_sec"], "Lax")
    print("Content-type: text/html")
    print("\n")
    print("Redirecting you to the authentication portal: " + redirect_url)
    sys.exit(0)


def get_token(code: str, config: dict[str, Any]):
    auth_context = adal.AuthenticationContext(config["adal_AUTHORITY_URL"])
    refresh_token = get_cookie(REFRESH_TOKEN)
    if refresh_token:
        return auth_context.acquire_token_with_refresh_token(
            refresh_token, config["adal_client_id"], config["adal_RESOURCE"], config["adal_client_secret"]
        )

    return auth_context.acquire_token_with_authorization_code(
        code, config["url"], config["adal_RESOURCE"], config["adal_client_id"], config["adal_client_secret"]
    )
