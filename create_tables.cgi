#!bin/python

# Create initial database tables
# PDF Review tool, created by Francois Botman, 2017.

import os
import re
import cgi
import sys
import json
import time
import glob
import string
import random
import MySQLdb

import config

if config.config["debug"]:
    import cgitb
    cgitb.enable()



def db_open():
    return MySQLdb.connect(host   = config.config["db_host"],
                           user   = config.config["db_user"],
                           passwd = config.config["db_passwd"],
                           db     = config.config["db_name"])


def db_close(conn):
    conn.close()


def db_create(dbconn = None):
    conn = dbconn if dbconn else db_open()
    cur  = conn.cursor()

    cur.execute("CREATE TABLE IF NOT EXISTS reviews   (id SERIAL PRIMARY KEY, reviewid TEXT, owner TEXT, closed BOOLEAN, pdffile TEXT, title TEXT);")
    cur.execute("CREATE TABLE IF NOT EXISTS comments  (id SERIAL PRIMARY KEY, hash TEXT, author TEXT, pageId INTEGER, type TEXT, msg TEXT, status TEXT, rects TEXT, replyToId TEXT, reviewid TEXT, timestamp INTEGER, deleted BOOLEAN);")
    cur.execute("CREATE TABLE IF NOT EXISTS myread    (id SERIAL PRIMARY KEY, commenthash TEXT, reviewid TEXT, reader TEXT, myread BOOLEAN);")
    cur.execute("CREATE TABLE IF NOT EXISTS myreviews (id SERIAL PRIMARY KEY, reviewid TEXT, reader TEXT);")
    cur.execute("CREATE TABLE IF NOT EXISTS activity  (id SERIAL PRIMARY KEY, owner TEXT, msg TEXT, url TEXT, timestamp INTEGER, reviewid TEXT);")
    cur.execute("CREATE TABLE IF NOT EXISTS errors    (id SERIAL PRIMARY KEY, msg TEXT, details TEXT, owner TEXT, reviewid TEXT);")

    conn.commit()
    cur.close()
    if not dbconn: db_close(conn)

print("Content-type: text/html\n")
print("Creating database tables...")
db_create()
print("done.")
