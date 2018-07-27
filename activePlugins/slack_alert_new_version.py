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
    script_name = os.environ["SGDAEMON_SLACKALERTS_NAME"]
    script_key = os.environ["SGDAEMON_SLACKALERTS_KEY"]

    # Grab an sg connection for the validator.
    sg = shotgun_api3.Shotgun(server, script_name=script_name, api_key=script_key)

    # Bail if our validator fails.
    if not is_valid(sg, reg.logger):
        reg.logger.warning("Plugin is not valid, will not register callback.")
        return

    eventFilter = {"Shotgun_Version_New": None}
    reg.registerCallback(
        script_name,
        script_key,
        new_version_alert,
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


def new_version_alert(sg, logger, event, args):
    """
    A callback that sends a slack alert to the project managers if a new
    version is created by a user.

    :param sg: Shotgun API handle.
    :param logger: Logger instance.
    :param event: A Shotgun EventLogEntry entity dictionary.
    :param args: Any additional misc arguments passed through this plugin.
    """

    # check to make sure the event has a project id. if not, bail
    if not event["project"]["id"]:
        return

    # query some project data
    proj_data = sg.find_one(
        "Project",
        [["id", "is", event["project"]["id"]]],
        ["id", "code", "sg_vfx_supervisor", "sg_cg_supervisors", "sg_producer", "sg_coordinator"]
    )

    # get the project managers
    managers = []
    if proj_data.get("sg_vfx_supervisor"):
        for vfx_supe in proj_data.get("sg_vfx_supervisor"):
            managers.append(vfx_supe)
    if proj_data.get("sg_cg_supervisor"):
        for cg_supe in proj_data.get("sg_cg_supervisor"):
            managers.append(cg_supe)
    if proj_data.get("sg_producer"):
        for producer in proj_data.get("sg_producer"):
            managers.append(producer)
    if proj_data.get("sg_coordinator"):
        for coord in proj_data.get("sg_coordinator"):
            managers.append(coord)

    # if theres no one to notify, then bail
    if not managers:
        return

    # if there's no event entity, then bail
    if not event["entity"]:
        return

    if event["user"]["type"] == "HumanUser":
        slack_id = slack_shotgun_bot.get_slack_user_id(sg, event["user"]["id"])
        if slack_id:
            user = "<@%s>" % slack_id
        else:
            user = event["user"]["name"]
        data = {
            'site': __SG_SITE,
            'user': user,
            'project': "<{}/page/project_overview?project_id={}|{}>".format(__SG_SITE, proj_data.get("id"), proj_data.get("code")),
            'version': "<{}/detail/Version/{}|{}>".format(__SG_SITE, event["entity"]["id"], event["entity"]["name"])
        }

        for manager in managers:
            slack_id = slack_shotgun_bot.get_slack_user_id(sg, manager["id"])
            if slack_id:
                message = "{user} has submitted version {project} / {version}".format(**data)
                slack_message = slack_shotgun_bot.send_message(slack_id, message)
                if slack_message["ok"]:
                    logger.info("New verison alert sent to {}.".format(manager["name"]))
                elif slack_message["error"]:
                    logger.warning("New version alert to {} failed to send with error: {}".format(manager["name"], slack_message["error"]))
