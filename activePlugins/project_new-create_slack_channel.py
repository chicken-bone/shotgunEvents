import os
import shotgun_api3
import slack_shotgun_bot
import time

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

    # Register our callback with the Shotgun_%s_Change event and tell the logger
    # about it.
    reg.registerCallback(
        script_name,
        script_key,
        createChannel,
        {"Shotgun_Project_New": None},
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

    # give shotgun 5 seconds to populate all the fields on the project
    # that was just created
    logger.debug("Waiting 2 seconds...")
    time.sleep(2)

    # gather some info
    project_id = event.get("meta", {}).get("entity_id")
    logger.debug("Got project ID {} from the event".format(project_id))

    # if for some reason the project id doesnt exist, then bail
    if not project_id:
        return

    proj_data = sg.find_one(
        "Project",
        [["id", "is", project_id]],
        ["code"]
    )

    if not proj_data:
        logger.info("Project data returned None. Skipping.")
        return

    channel_name = "proj-{}".format(proj_data["code"])

    logger.debug("Asking slack to create the new private channel {}".format(channel_name))
    new_channel = slack_shotgun_bot.create_channel(channel_name, private=True)

    if new_channel["ok"]:
        if new_channel.get("group").get("id"):
            channel_id = new_channel.get("group").get("id")
            channel_name = new_channel.get("group").get("name")
        else:
            channel_id = new_channel.get("channel").get("id")
            channel_name = new_channel.get("channel").get("name")
        logger.debug("New slack group made with name #{} and id {}".format(channel_name, channel_id))
        sg.update("Project", project_id, {"sg_slack_channel_id": channel_id})
    elif new_channel.get("error"):
        logger.warning("Slack channel was NOT created successfully with error: {}".format(new_channel["error"]))
