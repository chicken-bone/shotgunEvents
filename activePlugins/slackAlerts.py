import os
import logging
from slackclient import SlackClient


def registerCallbacks(reg):
    """
    Register all necessary or appropriate callbacks for this plugin.
    """

    eventFilter = {"Shotgun_Task_Change": "sg_status_list"}
    reg.registerCallback(
        os.environ["SGDAEMON_LOGARGS_NAME"],
        os.environ["SGDAEMON_LOGARGS_KEY"],
        slackAlert,
        eventFilter,
        None,
    )

    reg.logger.setLevel(logging.DEBUG)
    reg.logger.debug("Registered callback.")


def slackAlert(sg, logger, event, args):

    # logger.info("%s" % str(event))
    # logger.info("Event Type: %s" % str(event["event_type"]))
    slack_token = os.environ["SLACK_BOT_TOKEN"]
    sc = SlackClient(slack_token)

    if event["user"]["type"] == "HumanUser":
        slack_id = getSlackUserId(sg, sc, logger, event["user"]["id"])
        if slack_id:
            user = "<@%s>" % slack_id
        else:
            user = event["user"]["name"]
        data = {
            'project': event["project"]["name"],
            'user': user,
            'entity_type': event["entity"]["type"],
            'entity_id': event["entity"]["id"],
            'entity_name': event["entity"]["name"],
            'new_value': event["meta"]["new_value"]
        }

        sc.api_call(
            "chat.postMessage",
            channel="U1FU62WKS",
            as_user=True,
            text="Project: {project}\nDescription: {user} set <https://cbfx.shotgunstudio.com/detail/{entity_type}/{entity_id}|{entity_name}> to {new_value}.".format(**data)
        )


def getSlackUserId(sg, sc, logger, shotgun_id):

    sg_user = sg.find_one(
        "HumanUser",
        [["id", "is", shotgun_id]],
        ["email", "sg_slack_id"]
    )

    if sg_user["sg_slack_id"]:
        return sg_user["sg_slack_id"]
    else:
        slack_user = sc.api_call(
            "users.lookupByEmail",
            email=sg_user["email"]
        )

        # logger.debug("slack returned: %s" % str(slack_user))

        if slack_user["ok"]:
            slack_id = slack_user["user"]["id"]
            sg.update("HumanUser", shotgun_id, {"sg_slack_id": slack_id})
            return slack_id
        else:
            return None
