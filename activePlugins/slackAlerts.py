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


def slackAlert(sg, logger, event, args):

    # logger.info("%s" % str(event))
    # logger.info("Event Type: %s" % str(event["event_type"]))
    slack_token = os.environ["SLACK_BOT_TOKEN"]
    sc = SlackClient(slack_token)

    if event["user"]["type"] == "HumanUser":
        slack_user = getSlackUser(sg, sc, logger, event["user"]["id"])
        data = {
            'project': event["project"]["name"],
            'user_name': slack_user["username"],
            'slack_id': slack_user["id"],
            'entity_type': event["entity"]["type"],
            'entity_id': event["entity"]["id"],
            'entity_name': event["entity"]["name"],
            'new_value': event["meta"]["new_value"]
        }

        sc.api_call(
            "chat.postMessage",
            channel="U1FU62WKS",
            as_user=True,
            text="Project: {project}\nDescription: <@{slack_id}> set <https://cbfx.shotgunstudio.com/detail/{entity_type}/{entity_id}|{entity_name}> to {new_value}.".format(**data)
        )


def getSlackUser(sg, sc, logger, shotgun_id):

    sg_email = sg.find_one(
        "HumanUser",
        [["id", "is", shotgun_id]],
        ["email"]
    )["email"]

    # logger.info("email from shotgun: %s" % str(sg_email))

    slack_user = sc.api_call(
        "users.lookupByEmail",
        email=sg_email
    )

    # logger.info("slack returned: %s" % str(slack_user))

    if slack_user["ok"]:
        return {"id": slack_user["user"]["id"], "username": slack_user["user"]["name"]}
