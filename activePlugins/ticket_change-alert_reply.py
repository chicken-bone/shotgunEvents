import os
import shotgun_api3
import slack_shotgun_bot
import HTMLParser
parser = HTMLParser.HTMLParser()

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

    eventFilter = {"Shotgun_Ticket_Change": "replies"}
    reg.registerCallback(
        script_name,
        script_key,
        ticket_reply_alert,
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


def ticket_reply_alert(sg, logger, event, args):
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
    reply_added = event.get("meta", {}).get("added")

    # Bail if we don't have the info we need.
    if not event_project or not reply_added:
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
        ["title", "sg_ticket_type", "sg_priority", "description",
            "created_by", "sg_status_list", "sg_ticket_type",
            "addressings_cc", "addressings_to"]
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
        "title": "New reply on Ticket #{}: {}".format(ticket_data.get("id"), parser.unescape(ticket_data.get("title"))),
        "title_link": "{}/detail/Ticket/{}".format(__SG_SITE, ticket_data.get("id")),
        "text": parser.unescape(event.get("meta", {}).get("added")[0].get("name")),
        "author_name": ":writing_hand: {}".format(event.get("user")["name"]),
        "author_link": "{}/detail/HumanUser/{}".format(__SG_SITE, event.get("user")["id"]),
        "fields": [
            {
                "title": "Project",
                "value": proj_data.get("name"),
                "short": True
            },
            {
                "title": "Status",
                "value": ticket_status,
                "short": True
            },
        ]
    }]

    sg_users = ticket_data.get("addressings_to") + ticket_data.get("addressings_cc") + [ticket_data.get("created_by")]
    sg_users = [i for n, i in enumerate(sg_users) if i not in sg_users[n + 1:]]
    users = []
    for sg_user in sg_users:
        if sg_user == event.get("user"):
            pass
        elif sg_user["type"] == "HumanUser":
            users.append(sg_user)
        elif sg_user["type"] == "Group":
            group_users = sg.find_one(
                "Group",
                [["id", "is", sg_user["id"]]],
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
                logger.info("Ticket reply alert sent to {}.".format(user["name"]))
            elif slack_message["error"]:
                logger.warning("Ticket reply alert to {} failed to send with error: {}".format(user["name"], slack_message["error"]))

    # slack_id = "U1FU62WKS"
    # if slack_id:
    #     slack_message = slack_shotgun_bot.send_message(slack_id, None, attachments=attachments)
    #     if slack_message["ok"]:
    #         logger.info("Ticket reply alert sent to {}.".format(slack_id))
    #     elif slack_message["error"]:
    #         logger.warning("Ticket reply alert to {} failed to send with error: {}".format(slack_id, slack_message["error"]))
