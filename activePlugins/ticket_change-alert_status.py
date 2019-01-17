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

    args = {
        "ticket_status_field": "sg_status_list",
        "query_statuses": ["cmpt", "ip"],
    }

    # Grab an sg connection for the validator.
    sg = shotgun_api3.Shotgun(server, script_name=script_name, api_key=script_key)

    # Bail if our validator fails.
    if not is_valid(sg, reg.logger):
        reg.logger.warning("Plugin is not valid, will not register callback.")
        return

    eventFilter = {"Shotgun_Ticket_Change": args["ticket_status_field"]}
    reg.registerCallback(
        script_name,
        script_key,
        ticket_status_alert,
        eventFilter,
        args,
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


def ticket_status_alert(sg, logger, event, args):
    """
    A callback that sends a slack alert to users when a ticket is
    marked complete

    :param sg: Shotgun API handle.
    :param logger: Logger instance.
    :param event: A Shotgun EventLogEntry entity dictionary.
    :param args: Any additional misc arguments passed through this plugin.
    """

    # Return if we don't have all the field values we need.
    if not event.get("meta", {}).get("entity_id"):
        return

    # Make some vars for convenience.
    project_id = event["project"]["id"]
    entity_id = event["meta"]["entity_id"]

    # If the new value didnt change skip
    if event["meta"]["new_value"] == event["meta"]["old_value"]:
        logger.debug(
            "New value equals old value, skipping."
        )
        return

    # Re-query the Proejct to get necessary field values.
    project = sg.find_one(
        "Project",
        [["id", "is", project_id]],
        ["code", "name"]
    )

    # Return if we can't find the Project.
    if not project:
        logger.debug(
            "Could not find Project with id %s, skipping." % project_id
        )
        return

    # Re-query the Shot to get necessary field values.
    ticket = sg.find_one(
        "Ticket",
        [["id", "is", entity_id]],
        ["title", "sg_ticket_type", "sg_priority", "description",
            "created_by", "sg_status_list", "sg_ticket_type",
            "addressings_cc", "addressings_to"]
    )

    # Return if we can't find the Shot.
    if not ticket:
        logger.debug(
            "Could not find Ticket with id %s, skipping." % entity_id
        )
        return

    # Return if the shot status already changed
    if not ticket[args["ticket_status_field"]] == event["meta"]["new_value"]:
        logger.debug(
            "Tciekt status already no longer \"%s\", skipping." % event["meta"]["new_value"]
        )
        return

    # Return if the Shot status is not in the query_statuses list.
    if args.get("query_statuses") \
            and ticket[args["ticket_status_field"]] not in args["query_statuses"]:
        logger.debug("Ignoring ticket %s, status \"%s\" is not of allowed type(s): %s." % (
            ticket["id"],
            ticket[args["ticket_status_field"]],
            args["query_statuses"],
        )
        )
        return

    new_status = sg.find_one(
        "Status",
        [["code", "is", ticket.get("sg_status_list")]],
        ["name"]
    )["name"]

    # old_status = sg.find_one(
    #     "Status",
    #     [["code", "is", event["meta"]["old_value"]]],
    #     ["name"]
    # )["name"]

    if ticket.get("sg_priority").startswith("1"):
        priority_color = "danger"
    elif ticket.get("sg_priority").startswith("2"):
        priority_color = "warning"
    else:
        priority_color = "good"

    attachments = [{
        # "pretext": "Ticket alert:",
        "color": priority_color,
        "title": "Status changed on Ticket #{}: {}".format(ticket.get("id"), ticket.get("title")),
        "title_link": "{}/detail/Ticket/{}".format(__SG_SITE, ticket.get("id")),
        "author_name": ":writing_hand: {}".format(event.get("user")["name"]),
        "author_link": "{}/detail/HumanUser/{}".format(__SG_SITE, event.get("user")["id"]),
        "fields": [
            {
                "title": "Project",
                "value": project.get("name"),
                "short": True
            },
            {
                "title": "New Status",
                "value": new_status,
                "short": True
            },
        ]
    }]

    sg_users = ticket.get("addressings_to") + ticket.get("addressings_cc") + [ticket.get("created_by")]
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
                logger.info("Ticket status alert sent to {}.".format(user["name"]))
            elif slack_message["error"]:
                logger.warning("Ticket status alert to {} failed to send with error: {}".format(user["name"], slack_message["error"]))
