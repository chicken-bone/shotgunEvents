import os
import shotgun_api3
import slack_shotgun_bot

__SG_SITE = os.environ["SG_SERVER"]


def registerCallbacks(reg):
    """
    Register our callbacks.

    :param reg: A Registrar instance provided by the event loop handler.
    """

    # Grab authentication env vars for this plugin. Install these into the env
    # if they don't already exist.
    server = os.environ["SG_SERVER"]
    script_name = os.environ["SG_SCRIPT_NAME"]
    script_key = os.environ["SG_SCRIPT_KEY"]

    # Grab an sg connection for the validator.
    sg = shotgun_api3.Shotgun(server, script_name=script_name, api_key=script_key)

    # Bail if our validator fails.
    if not is_valid(sg, reg.logger):
        reg.logger.warning("Plugin is not valid, will not register callback.")
        return

    eventFilter = {"Shotgun_Task_Change": "task_assignees"}
    reg.registerCallback(
        script_name,
        script_key,
        task_assignment_alert,
        eventFilter,
        None,
    )
    reg.logger.debug("Registered callback.")


def is_valid(sg, logger):
    """
    Validate our args.

    :param sg: Shotgun API handle.
    :param logger: Logger instance.
    :returns: True if plugin is valid, None if not.
    """

    # Make sure we have a valid sg connection.
    try:
        sg.find_one("Project", [])
    except Exception, e:
        logger.warning(e)
        return

    return True


def task_assignment_alert(sg, logger, event, args):
    """
    A callback that sends a slack alert to the a user if they are assigned
    a new task on a project

    :param sg: Shotgun API handle.
    :param logger: Logger instance.
    :param event: A Shotgun EventLogEntry entity dictionary.
    :param args: Any additional misc arguments passed through this plugin.
    """

    # gather some info
    event_project = event.get("project")
    task_assignees = event.get("meta", {}).get("added")

    # Bail if we don't have the info we need.
    if not event_project or not task_assignees:
        return

    # query some project data
    proj_data = sg.find_one(
        "Project",
        [["id", "is", event["project"]["id"]]],
        ["code"]
    )

    task_data = sg.find_one(
        "Task",
        [["id", "is", event["entity"]["id"]]],
        ["content", "entity"]
    )

    task_link = task_data.get("entity")

    users = []
    for task_assignee in task_assignees:
        if task_assignee["type"] == "HumanUser":
            users.append(task_assignee)

    for user in users:
        slack_id = slack_shotgun_bot.get_slack_user_id(sg, user["id"])
        if slack_id:
            data = {
                'project': "<{}/page/project_overview?project_id={}|{}>".format(__SG_SITE, proj_data.get("id"), proj_data.get("code")),
                'task': "<{}/detail/Task/{}|{}>".format(__SG_SITE, task_data.get("id"), task_data.get("content")),
                'task_link': "<{}/detail/{}/{}|{}>".format(__SG_SITE, task_link["type"], task_link["id"], task_link["name"])
            }

            message = "You've been assigned {project} / {task_link} / {task}".format(**data)
            slack_message = slack_shotgun_bot.send_message(slack_id, message)
            if slack_message["ok"]:
                logger.info("New assignment alert sent to {}.".format(user["name"]))
            elif slack_message["error"]:
                logger.warning("New assignment alert to {} failed to send with error: {}".format(user["name"], slack_message["error"]))
