# main module of the tasks application

import json
import sqlite3

import os
import sys
import time

import config
import notify

DB_NAME = "tasks.db"

task_status = {
    None: "Nicht gefunden",
    "help": "Hilfeseite",
    "found": "Gefunden",
    "show": "Angezeigt",
    "done": "Erledigt",
    "veto": "Abgelehnt",
}


def list_all_tasks():
    """
    We return a list of all tasks for all users.
    """
    cfg = config.read_config()
    task_list = {}
    for user in cfg["users"]:
        task_list[user] = list_tasks(user=user)
    return task_list


def list_tasks(user="default_user"):
    """
    We return a list of all tasks for the given user, enriched with
    their status from the database.
    """
    tasks = json.load(open("tasks.json"))
    task_list = tasks[user]["tasks"]
    # now we need to enrich the tasks with information from the database
    create_db()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # we ask for all tasks with their actions
    cursor.execute(
        (
            "select distinct"
            "	t_main.id, "
            "	(select action_at from tasks where id = t_main.id and user = t_main.user and action = 'show') as shown_at, "
            "	(select action_at from tasks where id = t_main.id and user = t_main.user and action = 'veto') as vetoed_at, "
            "	(select action_at from tasks where id = t_main.id and user = t_main.user and action = 'done') as done_at "
            "from "
            "	tasks t_main "
            "where "
            "	user = ?;"
        ),
        (user,),
    )
    rows = cursor.fetchall()
    conn.close()
    for row in rows:
        task_id = row[0]
        shown_at = row[1]
        vetoed_at = row[2]
        done_at = row[3]
        # we find the task in the task_list by its id
        for task in task_list:
            if task["id"] == task_id:
                task["shown_at"] = shown_at
                task["vetoed_at"] = vetoed_at
                task["done_at"] = done_at
                break

    return task_list


def create_db(db_name=DB_NAME):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    sql_cmd = (
        "CREATE TABLE IF NOT EXISTS tasks ("
        "user TEXT,"
        "id TEXT,"
        "action_at TIMESTAMP,"
        "action TEXT,"
        "hash TEXT GENERATED ALWAYS AS (CONCAT(user,id,action)) STORED UNIQUE)"
    )
    cursor.execute(sql_cmd)
    conn.commit()
    conn.close()


def get_help_status(user, db_name=DB_NAME):
    """
    return True in case the help for the given user has been shown already
    """
    create_db(db_name=db_name)
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute(
        ("SELECT COUNT(*) " "FROM tasks " "WHERE user = ? AND action = 'help'"),
        (user,),
    )
    row = cursor.fetchone()
    conn.close()
    help_shown = row[0] if row else 0
    return help_shown > 0


def store_help(user, task, db_name=DB_NAME):
    """
    Store the time stamp of the help-display
    """
    if not task:
        task["id"] = "dummy"
        task["title"] = "Dummy Title"
    set_task_status(task=task, status="help", user=user, db_name=db_name)
    notification_email = config.read_config()["users"][user]["notify_email"]
    notify.send_notification_email(
        notification_email,
        subject="Help shown Notification",
        body=f"{user} has shown the help page on task: {task['title']}",
    )


def get_remaining_vetoes(user, db_name=DB_NAME):
    create_db(db_name=db_name)
    cfg = config.read_config()
    max_vetoes = cfg["vetoes"]
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute(
        ("SELECT COUNT(*) " "FROM tasks " "WHERE user = ? AND action = 'veto'"),
        (user,),
    )
    row = cursor.fetchone()
    conn.close()
    used_vetoes = row[0] if row else 0
    return max_vetoes - used_vetoes


def get_pending_task(user, db_name=DB_NAME):
    create_db(db_name=db_name)
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute(
        (
            "SELECT id "
            "FROM tasks "
            "WHERE user = ? AND action = 'show' "
            "AND id NOT IN ("
            "    SELECT id"
            "    FROM tasks"
            "    WHERE user = ? AND action IN ('done', 'veto'))"
        ),
        (user, user),
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        task_id = row[0]
        task_list = list_tasks(user=user)
        for idx, task in enumerate(task_list):
            if task["id"] == task_id:
                task["index"] = idx
                return task
    return None


def get_task_status(task, user=None, db_name=DB_NAME):
    """
    Get status of task for given user.
    This depends on the latest action taken on the task.

    :param user: Beschreibung
    :param task: Beschreibung
    """
    if user is None:
        user = task["user"]
    create_db(db_name=db_name)
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute(
        (
            "SELECT action_at, action "
            "FROM tasks "
            "WHERE user = ? AND id = ? "
            "ORDER BY action_at DESC "
            "LIMIT 1"
        ),
        (user, task["id"]),
    )
    row = cursor.fetchone()
    conn.close()
    # if we found an action, we return its status
    if row:
        return task_status[row[1]]
    # otherwise, we return None status
    return task_status[None]


def set_task_status(task, status, user=None, db_name=DB_NAME):
    """
    Set status of task for given user.

    :param user: Beschreibung
    :param task: Beschreibung
    :param status: Beschreibung
    """
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    # we allow only to insert an action once per task
    try:
        cursor.execute(
            (
                "INSERT INTO tasks "
                "(user, id, action_at, action) "
                "VALUES (?, ?, datetime('now'), ?)"
            ),
            (user, task["id"], status),
        )
    except sqlite3.IntegrityError:
        print(
            f"Task {task['id']} was already set to {status} before, not inserting again."
        )
    conn.commit()
    conn.close()


def show_task(user, id, db_name=DB_NAME):
    """
    We show the given task from the database.

    :param id: Beschreibung
    """
    create_db(db_name=db_name)
    tasks = list_tasks(user=user)
    notification_email = config.read_config()["users"][user]["notify_email"]
    task = tasks[id]
    task_status = get_task_status(task, user=user, db_name=db_name)
    # in case the task is not done or vetoed, we need to check for pending tasks
    if task_status not in ["Erledigt", "Abgelehnt"]:
        pending_task = get_pending_task(user, db_name=db_name)
        if pending_task is not None and pending_task != task["id"]:
            notify.send_notification_email(
                notification_email,
                subject="Task found Notification",
                body=(
                    f"{user} has found {task['title']} but cannot work on it yet, because {pending_task['title']} "
                    "has not been done or vetoed yet."
                ),
            )
            set_task_status(task, "found", user=user, db_name=db_name)
            return pending_task
    print(f"Showing task: {task['title']}")
    # we set the task to found and show, so that we can track that the user is working on it
    set_task_status(task, "found", user=user, db_name=db_name)
    time.sleep(1)  # we wait a bit to have a different timestamp for the show action
    set_task_status(task, "show", user=user, db_name=db_name)
    notify.send_notification_email(
        notification_email,
        subject="Task shown Notification",
        body=f"{user} is now working on task: {task['title']}",
    )
    return task


def do_task(user, id, db_name=DB_NAME):
    """
    We mark the given task as done in the database.

    :param id: Beschreibung
    """
    notification_email = config.read_config()["users"][user]["notify_email"]
    create_db(db_name=db_name)
    tasks = list_tasks(user=user)
    task = tasks[id]
    print(f"Doing task: {task['title']}")
    set_task_status(task, "done", user=user, db_name=db_name)
    notify.send_notification_email(
        notification_email,
        subject="Task done Notification",
        body=f"{user} has marked task {task['title']} as done.",
    )


def veto_task(user, id, db_name=DB_NAME):
    """
    We mark the given task as vetoed in the database.

    :param id: Beschreibung
    """
    create_db(db_name=db_name)
    notification_email = config.read_config()["users"][user]["notify_email"]
    tasks = list_tasks(user=user)
    task = tasks[id]
    # we need to check if we have remaining vetoes
    remaining_vetoes = get_remaining_vetoes(user, db_name=db_name)
    if remaining_vetoes <= 0:
        return False
    print(f"Vetoing task: {task['title']}")
    set_task_status(task, "veto", user=user, db_name=db_name)
    notify.send_notification_email(
        notification_email,
        subject="Task vetoed Notification",
        body=f"{user} has vetoed task {task['title']}",
    )
    return True


def main(argv):
    try:
        os.remove("test.db")
    except FileNotFoundError:
        print("test.db not found, continuing")
        pass
    print("argv:", argv)
    # we pick data from command line for testing
    token = argv[1]
    id = int(argv[2])
    other_id = int(argv[3])
    cfg = config.read_config()
    user = config.get_user_from_token(cfg, token)
    if not user:
        print("Invalid token")
        return

    # we're listing the tasks for the user
    tasks = list_tasks(user=user)
    print(f"Loaded tasks for user {user}: {tasks}")

    result = show_task(user, id, db_name="test.db")
    print("Result of show_task:", result)

    # showing a different task should fail as we have
    # the first task pending to be done or vetoed
    result = show_task(user, other_id, db_name="test.db")
    print("Result of show_task:", result)

    # we are marking the id as done in the database
    print("Attempting to do task id", id)
    do_task(user, id, db_name="test.db")
    do_task(user, id, db_name="test.db")

    # showing a different task should work now
    # as the previous task was done
    result = show_task(user, other_id, db_name="test.db")
    print("Result of show_task:", result)


if __name__ == "__main__":
    main(sys.argv)
