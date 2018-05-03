import os
import logging
from slackclient import SlackClient

__SG_SITE = os.environ["SG_SERVER"]


def registerCallbacks(reg):
    """
    Register all necessary or appropriate callbacks for this plugin.
    """

    eventFilter = {"Shotgun_Version_New": None, "Shotgun_Task_Change": "task_assignees"}
    reg.registerCallback(
        os.environ["SGDAEMON_SLACKALERTS_NAME"],
        os.environ["SGDAEMON_SLACKALERTS_KEY"],
        slackAlert,
        eventFilter,
        None,
    )

    reg.logger.setLevel(logging.DEBUG)
    reg.logger.debug("Registered callback.")


def slackAlert(sg, logger, event, args):

    slack_token = os.environ["SLACK_BOT_TOKEN"]
    sc = SlackClient(slack_token)

    if event["event_type"] == "Shotgun_Version_New":
        # alert sups and managers of new version published

        # example data:
        # 'attribute_name': None,
        # 'event_type': 'Shotgun_Version_New',
        # 'created_at': datetime.datetime(2018, 5, 1, 10, 34, 16, tzinfo=<shotgun_api3.lib.sgtimezone.LocalTimezone object at 0x103b497d0>),
        # 'entity': {'type': 'Version', 'id': 7265, 'name': 'test_version_v003'},
        # 'project': {'type': 'Project', 'id': 125, 'name': 'Development Episodic'},
        # 'meta': {'entity_id': 7265, 'type': 'new_entity', 'entity_type': 'Version'},
        # 'user': {'type': 'HumanUser', 'id': 88, 'name': 'Anthony Kramer'},
        # 'session_uuid': '773f76a4-4d65-11e8-8607-0242ac110004',
        # 'type': 'EventLogEntry',
        # 'id': 558746

        # get the project managers
        managers = getProjectManagers(sg, event["project"]["id"])

        # if theres no one to notify, then bail
        if not managers:
            return

        if not event["entity"] is None:
            if event["user"]["type"] == "HumanUser":
                slack_id = getSlackUserId(sg, sc, event["user"]["id"])
                if slack_id:
                    user = "<@%s>" % slack_id
                else:
                    user = event["user"]["name"]
                data = {
                    'site': __SG_SITE,
                    'user': user,
                    'project': "<{}/page/project_overview?project_id={}|{}>".format(__SG_SITE, event["project"]["id"], event["project"]["name"]),
                    'version': "<{}/detail/Version/{}|{}>".format(__SG_SITE, event["entity"]["id"], event["entity"]["name"])
                }

                for manager in managers:
                    slack_id = getSlackUserId(sg, sc, manager["id"])
                    if slack_id:
                        sc.api_call(
                            "chat.postMessage",
                            channel=slack_id,
                            as_user=True,
                            text="{user} has submitted version {version} on {project}".format(**data)
                        )

    if event["event_type"] == "Shotgun_Task_Change" and event["attribute_name"] == "task_assignees":

        # alert user of new task assignments

        # example data:
        # 'attribute_name': 'task_assignees',
        # 'event_type': 'Shotgun_Task_Change',
        # 'created_at': datetime.datetime(2018, 5, 1, 15, 57, 11, tzinfo=<shotgun_api3.lib.sgtimezone.LocalTimezone object at 0x10eac77d0>),
        # 'entity': {'type': 'Task', 'id': 6391, 'name': 'Lighting'},
        # 'project': {'type': 'Project', 'id': 125, 'name': 'Development Episodic'},
        # 'meta': {'entity_id': 6391, 'added': [{'status': 'act', 'valid': 'valid', 'type': 'HumanUser', 'name': 'Anthony Kramer', 'id': 88}], 'attribute_name': 'task_assignees', 'entity_type': 'Task', 'field_data_type': 'multi_entity', 'removed': [], 'type': 'attribute_change'},
        # 'user': {'type': 'HumanUser', 'id': 88, 'name': 'Anthony Kramer'},
        # 'session_uuid': 'f90c27a4-4d92-11e8-a0e2-0242ac110004',
        # 'type': 'EventLogEntry',
        # 'id': 560807

        event_project = event.get("project")
        task_assignees = event.get("meta", {}).get("added")

        # Bail if we don't have the info we need.
        if not event_project or not task_assignees:
            return

        users = []
        for task_assignee in task_assignees:
            if task_assignee["type"] == "HumanUser":
                users.append(task_assignee)

        for user in users:
            slack_id = getSlackUserId(sg, sc, user["id"])
            if slack_id:
                data = {
                    'project': "<{}/page/project_overview?project_id={}|{}>".format(__SG_SITE, event["project"]["id"], event["project"]["name"]),
                    'task': "<{}/detail/Task/{}|{}>".format(__SG_SITE, event["entity"]["id"], event["entity"]["name"])
                }

                sc.api_call(
                    "chat.postMessage",
                    channel=slack_id,
                    as_user=True,
                    text="You've been assigned {task} on {project}".format(**data)
                )

    # if event["user"]["type"] == "HumanUser":
    #     slack_id = getSlackUserId(sg, sc, event["user"]["id"])
    #     if slack_id:
    #         user = "<@%s>" % slack_id
    #     else:
    #         user = event["user"]["name"]
    #     data = {
    #         'site': __SG_SITE,
    #         'project': event["project"]["name"],
    #         'user': user,
    #         'entity_type': event["entity"]["type"],
    #         'entity_id': event["entity"]["id"],
    #         'entity_name': event["entity"]["name"],
    #         'new_value': event["meta"]["new_value"]
    #     }
    #
    #     sc.api_call(
    #         "chat.postMessage",
    #         channel="U1FU62WKS",
    #         as_user=True,
    #         text="Project: {project}\nDescription: {user} set <{site}/detail/{entity_type}/{entity_id}|{entity_name}> to {new_value}.".format(**data)
    #     )


def getSlackUserId(sg, sc, shotgun_id):

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

        if slack_user["ok"]:
            slack_id = slack_user["user"]["id"]
            sg.update("HumanUser", shotgun_id, {"sg_slack_id": slack_id})
            return slack_id
        else:
            return None


def getProjectManagers(sg, project_id):

    proj_data = sg.find_one(
        "Project",
        [["id", "is", project_id]],
        ["sg_vfx_supervisor", "sg_cg_supervisors", "sg_producer"]
    )
    managers = []
    try:
        for vfx_supe in proj_data["sg_vfx_supervisor"]:
            managers.append(vfx_supe)
    except KeyError:
        pass
    try:
        for cg_supe in proj_data["sg_cg_supervisor"]:
            managers.append(cg_supe)
    except KeyError:
        pass
    try:
        for producer in proj_data["sg_producer"]:
            managers.append(producer)
    except KeyError:
        pass
    return managers
