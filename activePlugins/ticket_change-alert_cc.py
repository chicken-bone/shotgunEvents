import os
import shotgun_api3
import slack_shotgun_bot
from parse_html import parseHtml

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

    eventFilter = {"Shotgun_Ticket_Change": "addressings_cc"}
    reg.registerCallback(
        script_name,
        script_key,
        ticket_cc_alert,
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


def ticket_cc_alert(sg, logger, event, args):
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
    ticket_ccs = event.get("meta", {}).get("added")

    # Bail if we don't have the info we need.
    if not event_project or not ticket_ccs:
        return

    # query some project data
    proj_data = sg.find_one(
        "Project",
        [["id", "is", event["project"]["id"]]],
        ["code", "name"]
    )

    ticket_data = sg.find_one(
        "Ticket",
        [["id", "is", event["entity"]["id"]]],
        ["title", "sg_ticket_type", "sg_priority", "description", "created_by", "sg_status_list", "sg_ticket_type"]
    )

    ticket_status = sg.find_one(
        "Status",
        [["code", "is", ticket_data.get("sg_status_list")]],
        ["name"]
    )["name"]

    if ticket_data.get("sg_priority").startswith("1"):
        priority_color = "danger"
    elif ticket_data.get("sg_priority").startswith("2"):
        priority_color = "warning"
    else:
        priority_color = "good"

    attachments = [{
        # "pretext": "Ticket alert:",
        "color": priority_color,
        "title": "You've been CC'd on Ticket #{}: {}".format(ticket_data.get("id"), parseHtml(ticket_data.get("title"))),
        "title_link": "{}/detail/Ticket/{}".format(__SG_SITE, ticket_data.get("id")),
        "text": parseHtml(ticket_data.get("description")),
        "author_name": ":writing_hand: {}".format(ticket_data.get("created_by")["name"]),
        "author_link": "{}/detail/HumanUser/{}".format(__SG_SITE, ticket_data.get("created_by")["id"]),
        "fields": [
            {
                "title": "Project",
                "value": proj_data.get("name"),
                "short": True
            },
            {
                "title": "Priority",
                "value": ticket_data.get("sg_priority"),
                "short": True
            },
            {
                "title": "Status",
                "value": ticket_status,
                "short": True
            },
            {
                "title": "Type",
                "value": ticket_data.get("sg_ticket_type"),
                "short": True
            },
        ]
    }]

    users = []
    for ticket_cc in ticket_ccs:
        if ticket_cc == event.get("user"):
            pass
        elif ticket_cc["type"] == "HumanUser":
            users.append(ticket_cc)
        elif ticket_cc["type"] == "Group":
            group_users = sg.find_one(
                "Group",
                [["id", "is", ticket_cc["id"]]],
                ["users"]
            )
            for group_user in group_users["users"]:
                if group_user == event.get("user"):
                    pass
                else:
                    users.append(group_user)

    for user in users:
        slack_id = slack_shotgun_bot.get_slack_user_id(sg, user["id"])
        if slack_id:
            slack_message = slack_shotgun_bot.send_message(slack_id, None, attachments=attachments)
            if slack_message["ok"]:
                logger.info("New cc alert sent to {}.".format(user["name"]))
            elif slack_message["error"]:
                logger.warning("New cc alert to {} failed to send with error: {}".format(user["name"], slack_message["error"]))

    # slack_id = "U1FU62WKS"
    # if slack_id:
    #     slack_message = slack_shotgun_bot.send_message(slack_id, None, attachments=attachments)
    #     if slack_message["ok"]:
    #         logger.info("New assignment alert sent to {}.".format(slack_id))
    #     elif slack_message["error"]:
    #         logger.warning("New assignment alert to {} failed to send with error: {}".format(slack_id, slack_message["error"]))
