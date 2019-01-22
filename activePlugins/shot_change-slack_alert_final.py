import os
import shotgun_api3
import slack_shotgun_bot
import random

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
        "shot_status_field": "sg_status_list",
        "query_statuses": ["cmpt"],
    }
    # Grab an sg connection for the validator.
    sg = shotgun_api3.Shotgun(server, script_name=script_name, api_key=script_key)

    # Bail if our validator fails.
    if not is_valid(sg, reg.logger):
        reg.logger.warning("Plugin is not valid, will not register callback.")
        return

    eventFilter = {"Shotgun_Shot_Change": args["shot_status_field"]}
    reg.registerCallback(
        script_name,
        script_key,
        shot_finaled_alert,
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


def shot_finaled_alert(sg, logger, event, args):
    """
    A callback that sends a slack alert the project channel when a
    shot entity has been marked complete

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
        ["code", "sg_slack_channel_id"]
    )

    # Return if we can't find the Project.
    if not project:
        logger.debug(
            "Could not find Project with id %s, skipping." % entity_id
        )
        return

    if not project.get("sg_slack_channel_id"):
        logger.debug(
            "Project does not have a slack channel id, skipping."
        )
        return

    # Re-query the Shot to get necessary field values.
    shot = sg.find_one(
        "Shot",
        [["id", "is", entity_id]],
        ["code", args["shot_status_field"]]
    )

    # Return if we can't find the Shot.
    if not shot:
        logger.debug(
            "Could not find Shot with id %s, skipping." % entity_id
        )
        return

    # Return if the shot status already changed
    if not shot[args["shot_status_field"]] == event["meta"]["new_value"]:
        logger.debug(
            "Shot status already no longer \"%s\", skipping." % event["meta"]["new_value"]
        )
        return

    # Return if the Shot status is not in the query_statuses list.
    if args.get("query_statuses") \
            and shot[args["shot_status_field"]] not in args["query_statuses"]:
        logger.debug("Ignoring %s, status \"%s\" is not of allowed type(s): %s." % (
            shot["code"],
            shot[args["shot_status_field"]],
            args["query_statuses"],
        )
        )
        return

    emoji_list = [":tada:", ":+1:", ":sunglasses:", ":beer:", ":trophy:", ":fire:", ":cat:"]

    data = {
        'shot': "<{}/detail/Shot/{}|{}>".format(__SG_SITE, shot.get("id"), shot.get("code")),
        'emoji': random.choice(emoji_list)
    }

    message = "{emoji} Shot *{shot}* has been finaled!".format(**data)
    slack_message = slack_shotgun_bot.send_message(project.get("sg_slack_channel_id"), message)
    if slack_message["ok"]:
        logger.info("Shot final alert sent to {}.".format(project.get("sg_slack_channel_id")))
    elif slack_message["error"]:
        logger.warning("Shot final alert to {} failed to send with error: {}".format(project.get("sg_slack_channel_id"), slack_message["error"]))
