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
    Register our callbacks.

    :param reg: A Registrar instance provided by the event loop handler.
    """

    # filter for login events and register the callback
    eventFilter = {'Shotgun_User_Login': None}
    reg.registerCallback(
        os.environ["SGDAEMON_RECORDLOGIN_NAME"],
        os.environ["SGDAEMON_RECORDLOGIN_KEY"],
        record_login,
        eventFilter,
        None,
    )

    reg.logger.setLevel(logging.DEBUG)
    reg.logger.debug("Registered callback.")


def record_login(sg, logger, event, args):
    """
    A callback that records the users login datetime to thier user record on
    in shotgun.

    :param sg: Shotgun API handle.
    :param logger: Logger instance.
    :param event: A Shotgun EventLogEntry entity dictionary.
    :param args: Any additional misc arguments passed through this plugin.
    """
    # logger.debug("%s" % str(event))
    user_name = event["entity"]["name"]
    user_id = event["entity"]["id"]
    login_time = event["created_at"]

    sg.update("HumanUser", user_id, {"sg_last_login": login_time})
    logger.debug("Recorded user login datetime for user %s" % user_name)
