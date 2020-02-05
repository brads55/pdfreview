#!bin/python

###################################################################################
# Backup database
###################################################################################

import os
import config
import argparse
from datetime import date


# Handlers for different backings:
commands = {
    'mysql': 'mysqldump --add-drop-database -h {db_host} -u {db_user} -p{db_password} {db_name} > {output}',
    'postgresql': 'PGPASSWORD="{db_password} pg_dump --clean --create -f {output} -h {db_host} -d {db_name} -U {db_user}'
}

# Argparse handler for directories
class directory(argparse.Action):
    def __call__(self, parser, namespace, dirname, option_string=None):
        if not os.path.isdir(dirname):
            raise argparse.ArgumentTypeError("directory:{0} is not a valid path".format(dirname))
        setattr(namespace, self.dest, dirname.rstrip(os.path.sep))


def main():
    parser = argparse.ArgumentParser(description='PDFReview database backup')
    parser.add_argument('--engine', choices=commands.keys(), required=True)
    parser.add_argument('dest', action=directory)
    args = parser.parse_args()

    today = date.today()
    dumpcmd = commands[args.engine].format(
            db_host     = config.config["db_host"],
            db_user     = config.config["db_user"],
            db_password = config.config["db_passwd"],
            db_name     = config.config["db_name"],
            output      = (args.dest + os.path.sep + today.strftime("%Y_%m_%d") + '.sql')
    )
    os.system(dumpcmd)

if __name__ == '__main__':
    main()
