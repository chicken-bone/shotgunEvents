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
    script_name = os.environ["SGDAEMON_SLACKCHANNELS_NAME"]
    script_key = os.environ["SGDAEMON_SLACKCHANNELS_KEY"]

    # Grab an sg connection for the validator.
    sg = shotgun_api3.Shotgun(server, script_name=script_name, api_key=script_key)

    # Bail if our validator fails.
    if not is_valid(sg, reg.logger):
        reg.logger.warning("Plugin is not valid, will not register callback.")
        return

    event_filter = {"Shotgun_Project_Change": ["users", "sg_vfx_supervisor", "sg_cg_supervisor", "sg_producer", "sg_coordinator"]}

    # Register our callback with the Shotgun_%s_Change event and tell the logger
    # about it.
    reg.registerCallback(
        script_name,
        script_key,
        createChannel,
        event_filter,
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


def createChannel(sg, logger, event, args):

    # {'attribute_name': None,
    # 'event_type': 'Shotgun_Project_New',
    # 'created_at': datetime.datetime(2018, 5, 3, 18, 2, 58, tzinfo=<shotgun_api3.lib.sgtimezone.LocalTimezone object at 0x1071f4850>),
    # 'entity': {'type': 'Project', 'id': 133, 'name': 'slackProject'},
    # 'project': None,
    # 'meta': {'entity_id': 133, 'type': 'new_entity', 'entity_type': 'Project'},
    # 'user': {'type': 'HumanUser', 'id': 88, 'name': 'Anthony Kramer'},
    # 'session_uuid': 'c521519e-4f36-11e8-bc45-0242ac110004',
    # 'type': 'EventLogEntry',
    # 'id': 568623}

    # gather some info
    project_id = event.get("meta", {}).get("entity_id")
    users_added = event.get("meta", {}).get("added")
    users_removed = event.get("meta", {}).get("removed")
    logger.debug("Got project ID {} from the event".format(project_id))

    # if for some reason the project id doesnt exist, then bail
    if not project_id:
        return

    proj_data = sg.find_one(
        "Project",
        [["id", "is", project_id]],
        ["sg_slack_channel_id"]
    )

    if not proj_data:
        logger.info("Project data returned None. Skipping.")
        return

    if not proj_data.get("sg_slack_channel_id"):
        logger.info("Project {} does not have a slack channel entry.")
        return

    slack_channel = proj_data["sg_slack_channel_id"]

    for user in users_added:
        if user["type"] == "HumanUser":
            slack_id = slack_shotgun_bot.get_slack_user_id(sg, user["id"])
            invite = slack_shotgun_bot.invite_to_channel(slack_id, slack_channel)
            if invite["ok"]:
                logger.info("User {} added to slack channel {}.".format(user["name"], slack_channel))
            elif invite.get("error"):
                logger.info("Failed to add user {}({}) to slack channel {} wth error: {}".format(user["name"], slack_id, slack_channel, invite["error"]))

    for user in users_removed:
        if user["type"] == "HumanUser":
            slack_id = slack_shotgun_bot.get_slack_user_id(sg, user["id"])
            kick = slack_shotgun_bot.kick_from_channel(slack_id, slack_channel)
            if kick["ok"]:
                logger.info("User {} removed from slack channel {}.".format(user["name"], slack_channel))
            elif kick.get("error"):
                logger.info("Failed to remove user {} from slack channel {} wth error: {}".format(user["name"], slack_channel, kick["error"]))
