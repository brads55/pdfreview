#!bin/python

import os
import re
import sys
import MySQLdb


#
# Database functions ---------------------------------------------------------------------------------
#

def db_open(config):
    return MySQLdb.connect(host   = config["db_host"],
                           user   = config["db_user"],
                           passwd = config["db_passwd"],
                           db     = config["db_name"],
                           charset='utf8mb4')

def db_close(conn):
    conn.close()

#
# Support functions ----------------------------------------------------------------------------------
#

def print_file(filename, substitutions, config):
    """Prints out the file specified to the standard output, performing any requested substitutions.
       The substitutions are in the form [[r'regex', 'replacement'], ...]"""
    substitutions.append([r'%BRANDING%', config["branding"]])
    f = open(filename, 'r')
    for line in f:
        for substitution in substitutions:
            line = re.sub(substitution[0], substitution[1], line)
        sys.stdout.write(line)
    f.close()

