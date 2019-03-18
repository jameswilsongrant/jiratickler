#!/usr/local/bin/python3
""" Tickler program to run in a loop and yell at me if something changes on a ticket I'm watching """
from jira import JIRA
import argparse
import sqlite3
import configparser
import json
import hashlib
import time

CONFIG = configparser.ConfigParser()
CONFIG.read('config.ini')


def GetIssueHash(id):
    """ Inspect our issue/comments and return a hash value. We don't want to store issues locally in case there is sensitive data in them """
    j = JIRA(basic_auth=(str(CONFIG['jira']['username']), str(
        CONFIG['jira']['password'])), options={'server': str(CONFIG['jira']['server'])})
    issue = j.issue(id)
    issue_object = {"id": id, "server": str(CONFIG['jira']['server']), "created": str(issue.fields.created), "status": str(
        issue.fields.status), "description": str(issue.fields.description), "comments": []}

    comments = j.comments(issue)
    for c in comments:
        comment_object = {"created": str(c.created), "updated": str(
            c.updated), "author": str(c.author), "body": str(c.body)}
        issue_object['comments'].append(comment_object)

    m = hashlib.md5()
    m.update(json.dumps(issue_object).encode('utf-8'))

    if ARGS.verbose:
        print("Ticket ID: " + id + " Hash: " + m.hexdigest())

    return m.hexdigest()


def CompareIssueHash(id, db):
    """ Check a ticket id against what we have stored or add it if the id isn't found """
    conn = sqlite3.connect(db)
    c = conn.cursor()
    issue_hash = GetIssueHash(id)
    c.execute("SELECT md5 FROM issues WHERE id=?", (id,))
    try:
        stored_hash = c.fetchone()[0]
    except TypeError:
        if ARGS.verbose:
            print("Not found, adding to " + db)
        c.execute('INSERT INTO issues VALUES (?,?)', (id, issue_hash))
        conn.commit()
        conn.close()
        return True
    if ARGS.verbose:
        print("Current Issue Hash: " + issue_hash)
        print("Stored Issue Hash: " + stored_hash)
    conn.close()
    return issue_hash == stored_hash


def RunComparison(db):
    """ Run our happy path comparison checks """
    for entry in CONFIG['tickets']:
        id = CONFIG['tickets'][entry]
        if ARGS.verbose:
            print("Comparing Ticket ID " + id + " to " + db)
        if not CompareIssueHash(id, db):
            try:
                while True:
                    print("Ticket ID " + id +
                          " has changed! (Ctrl C to update and continue)\a")
                    time.sleep(1)
            except KeyboardInterrupt:
                print("Updating " + db + " for Ticket ID " + id + "... ", end='')
                conn = sqlite3.connect(db)
                c = conn.cursor()
                c.execute("UPDATE issues SET md5 = ? WHERE id = ?",
                          (GetIssueHash(id), id))
                conn.commit()
                conn.close()
                print("Done!")
    if ARGS.verbose:
        print("Done checking tickets. Exiting...")


def InitializeDB(db):
    """ Wipe our database file and load our initial md5s """
    print("Initializing " + db)
    conn = sqlite3.connect(db)
    c = conn.cursor()
    try:
        c.execute('''DROP TABLE issues''')
    except sqlite3.OperationalError:
        pass
    c.execute('''CREATE TABLE issues (id text, md5 text)''')
    conn.commit()

    for entry in CONFIG['tickets']:
        id = CONFIG['tickets'][entry]
        print("Adding Ticket ID: " + id)
        checksum = GetIssueHash(id)
        c.execute('INSERT INTO issues VALUES (?,?)', (id, checksum))
    conn.commit()

    conn.close()
    print("Done. New tickets added to the config file will be hashed and added automatically. Exiting...")
    exit()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Monitor a list of Jira tickets for changes and bell if any are found.")
    parser.add_argument(
        "--verbose", help="Be verbose. Otherwise this script runs without output.", action="store_true")
    parser.add_argument(
        "--init", help="Wipe and initialize the sqlite database", action="store_true")
    global ARGS
    ARGS = parser.parse_args()
    if ARGS.init:
        InitializeDB('jiratickler.sqlite')

    RunComparison('jiratickler.sqlite')
