# Copyright 2018 Autodesk, Inc.  All rights reserved.
#
# Use of this software is subject to the terms of the Autodesk license agreement
# provided at the time of installation or download, or which otherwise accompanies
# this software in either electronic or hard copy form.
#

# See docs folder for detailed usage info.

import os
import logging


def registerCallbacks(reg):
    """
    Register all necessary or appropriate callbacks for this plugin.
    """
    # eventFilter = {'Shotgun_Task_Change': ['sg_status_list']}
    eventFilter = {'Shotgun_User_Login': None}
    reg.registerCallback(
        os.environ["SGDAEMON_RECORDLOGIN_NAME"],
        os.environ["SGDAEMON_RECORDLOGIN_KEY"],
        record_login,
        eventFilter,
        None,
    )

    # Set the logging level for this particular plugin. Let debug and above
    # messages through (don't block info, etc). This is particularly usefull
    # for enabling and disabling debugging on a per plugin basis.
    reg.logger.setLevel(logging.DEBUG)
    reg.logger.debug("Registered callback.")


def record_login(sg, logger, event, args):
    """
    A callback that logs its arguments.

    :param sg: Shotgun API handle.
    :param logger: Logger instance.
    :param event: A Shotgun EventLogEntry entity dictionary.
    :param args: Any additional misc arguments passed through this plugin.
    """
    # logger.info("%s" % str(event))
    user_id = event["entity"]["id"]
    login_time = event["created_at"]

    sg.update("HumanUser", user_id, {"sg_last_login": login_time})
