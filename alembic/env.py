# PDF review stores its configuration in the parent directory's config.py file
import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

currentdir = os.path.dirname(os.path.abspath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0, parentdir)
from urllib.parse import quote_plus

import config as pdfreview_config

if sys.stdout.encoding.upper() != "UTF-8":
    print("Unsupported environment. Locale does not use utf-8. Is LC_ALL set to the right value?", file=sys.stderr)
    print("    Current encoding: " + sys.stdout.encoding, file=sys.stderr)
    sys.exit(1)


# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = None

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_connection_url():
    c = pdfreview_config.config
    url = "mysql://{}:{}@{}/{}?charset=utf8mb4".format(
        *[quote_plus(s) for s in [c["db_user"], c["db_passwd"], c["db_host"], c["db_name"]]]
    )
    return url


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    raise Exception("Offline migrations are not supported by this script")
    # url = get_connection_url()
    # context.configure(
    #    url=url,
    #    target_metadata=target_metadata,
    #    literal_binds=True,
    #    dialect_opts={"paramstyle": "named"},
    # )

    # with context.begin_transaction():
    #    context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    ini_section = config.get_section(config.config_ini_section)
    ini_section["sqlalchemy.url"] = get_connection_url()
    connectable = engine_from_config(
        ini_section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
