#!bin/python

#from adal import AuthenticationContext

#auth_context = AuthenticationContext("https://login.microsoftonline.com/contoso.onmicrosoft.com")



import os
import cgi
import sys
import cgitb
import adal
import uuid
import json
import time
import requests
import MySQLdb

from common import *


TOKEN_NAME = "adal-token"
REFRESH_TOKEN = "adal-refresh-token"
UUID_TOKEN = "adal-auth-session"


def login(config):
    try:
        form   = cgi.FieldStorage()
        code   = form.getvalue("code")
        state  = form.getvalue("state")
        err    = form.getvalue("error")
        errmsg = form.getvalue("error_description")

        config["adal_AUTHORITY_URL"] = config["adal_authority_host"] + '/' + config["adal_tenant"]
        config["adal_RESOURCE"]      = "https://graph.microsoft.com"
        config["adal_session_state_timeout_sec"] = 5 * 60 * 60


        if config["debug"]:
            cgitb.enable()

        #
        # If the user has a valid token, validate that now
        #
        cookie = get_cookie(TOKEN_NAME)
        if cookie:
            # Perform database token expiration maintenance
            db = db_open(config)
            cur = db.cursor()
            cur.execute("DELETE FROM adal_auth WHERE expire<%s;", (int(time.time()),))
            db.commit()

            # Find user in table
            cur.execute("SELECT name, email from adal_auth WHERE authkey=%s;", (cookie,))
            result = cur.fetchone()
            cur.close()
            db_close(db)

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

            state_ref = get_cookie(UUID_TOKEN)
            if (state_ref != state):
                auth_error("The session states for ADAL authentication do not match, possible CSI breach. Expected {}, got {}".format(state_ref, state), config)
            token = get_token(code, config)

            headers = {'Content-Type':'application/json', 'Authorization':'Bearer {0}'.format(token['accessToken'])}
            endpoint = "https://graph.microsoft.com/v1.0/me/"
            response = requests.get(endpoint, headers=headers)

            if response.status_code == 200:
                json_data = json.loads(response.text)
                username  = json_data["displayName"]
                useremail = json_data["mail"]
                user_key  = uuid.uuid1()

                db = db_open(config)
                cur = db.cursor()
                cur.execute("INSERT INTO adal_auth (authkey, name, email, expire) VALUES (%s, %s, %s, %s);", (
                        user_key,
                        username,
                        useremail,
                        int(time.time() + config["adal_expires_sec"])))
                db.commit()
                cur.close()
                db_close(db)

                print("Status: 307 Redirect")
                print("Location: " + config["url"])
                set_cookie(TOKEN_NAME, user_key, config["adal_expires_sec"], "Lax")
                set_cookie(REFRESH_TOKEN, token["refreshToken"], config["adal_session_state_timeout_sec"], "Lax")
                print("\n")

            else:
                auth_error("ADAL endpoint request resulted in a {} error ({})".format(response.status_code, response.text), config)
            sys.exit(0)

        #
        # Otherwise, redirect to authentication interface
        #
        redirect_to_portal(config)
        sys.exit(0)

    except adal.AdalError as e:
        auth_error("Adal exception error: " + str(e), config)



def auth_error(msg, config):
    print("Content-type: text/html\n")
    print_file("./auth_error.html.template", [[r'%ERROR_MESSAGE%', msg]], config)
    sys.exit(0)

def get_cookie(name):
    if 'HTTP_COOKIE' in os.environ:
        for cookie in map(str.strip, str.split(os.environ['HTTP_COOKIE'], ';')):
            (key, value ) = str.split(cookie, '=', 1)
            if key == name:
                return value
    return None

def set_cookie(name, value, expires_seconds, policy = "Strict"):
    """This should come after a Content-type response"""
    print("Set-Cookie: {name}={value}; SameSite={policy}; Max-age={expires_seconds};".format(**locals()))


def redirect_to_portal(config):
    session_state = uuid.uuid1()
    redirect_url  = ('https://login.microsoftonline.com/{}/oauth2/authorize?' +
                        'response_type=code&client_id={}&redirect_uri={}&state={}&resource={}').format(
                                config["adal_tenant"],
                                config["adal_client_id"],
                                config["url"],
                                session_state,
                                config["adal_RESOURCE"])
    print("Status: 307 Redirect")
    print("Location: " + redirect_url)
    set_cookie(UUID_TOKEN, session_state, config["adal_session_state_timeout_sec"], "Lax")
    print("Content-type: text/html")
    print("\n")
    print("Redirecting you to the authentication portal: " + redirect_url)
    sys.exit(0)


def get_token(code, config):
    auth_context   = adal.AuthenticationContext(config["adal_AUTHORITY_URL"])
    refresh_token = get_cookie(REFRESH_TOKEN)
    if refresh_token:
        return auth_context.acquire_token_with_refresh_token(refresh_token, config["adal_client_id"],
                config["adal_RESOURCE"], config["adal_client_secret"])
    else:
        return auth_context.acquire_token_with_authorization_code(code, config["url"], config["adal_RESOURCE"],
                config["adal_client_id"], config["adal_client_secret"])

