#!/usr/bin/env bash
""":"

echo -e "Content-Type: text/plain\n"
if [ "$PDFREVIEW_TESTING_ENABLED" != "true" ]; then
    echo "Test DB access is disabled"
    exit 1;
fi

source venv/bin/activate

echo reset database
alembic downgrade base
alembic upgrade head
echo done

exit
"""
import os; os.execv( __file__ , [__file__]);
