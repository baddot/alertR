#!/usr/bin/python3

# written by sqall
# twitter: https://twitter.com/sqall01
# blog: https://h4des.org
# github: https://github.com/sqall01
#
# Licensed under the GNU Affero General Public License, version 3.

import time
import logging
import os
import threading
from typing import Optional
from .communication import Promise
from .serverCommunication import ServerCommunication
from ..smtp import SMTPAlert


# this class checks if the connection to the server has broken down
# => reconnects it if necessary
class ConnectionWatchdog(threading.Thread):

    def __init__(self,
                 connection: ServerCommunication,
                 pingInterval: int,
                 smtpAlert: Optional[SMTPAlert]):

        threading.Thread.__init__(self)

        # the object that handles the communication with the server
        self._connection = connection

        # the interval in which a ping should be send when no data
        # was received in this time
        self._ping_interval = pingInterval

        # the object to send a email alert via smtp
        self._smtp_alert = smtpAlert

        # the file name of this file for logging
        self._log_tag = os.path.basename(__file__)

        # set exit flag as false
        self._exit_flag = False

        # internal counter to get the current count of connection retries
        self._connection_retries = 1

    def run(self):
        """
        Connection watchdog loop that checks the communication channel to the server.
        :return:
        """

        # check every 5 seconds if the client is still connected
        # and the time of the last received data
        # from the server lies too far in the past
        while True:

            # wait 5 seconds before checking time of last received data
            for i in range(5):
                if self._exit_flag:
                    logging.info("[%s]: Exiting Connection Watchdog." % self._log_tag)
                    return
                time.sleep(1)

            # check if the client is still connected to the server
            if not self._connection.is_connected:

                logging.error("[%s]: Connection to server has died. " % self._log_tag)

                # Reconnect to the server.
                while True:

                    # Check if 5 unsuccessful attempts are made to connect
                    # to the server and if smtp alert is activated
                    # => send eMail alert
                    if self._smtp_alert is not None and (self._connection_retries % 5) == 0:
                        self._smtp_alert.sendCommunicationAlert(self._connection_retries)

                    # try to connect to the server
                    if self._connection.reconnect():
                        # if smtp alert is activated
                        # => send email that communication problems are solved
                        if self._smtp_alert is not None:
                            self._smtp_alert.sendCommunicationAlertClear()

                        logging.info("[%s] Reconnecting successful after %d attempts."
                                     % (self._log_tag, self._connection_retries))

                        self._connection_retries = 1
                        break

                    self._connection_retries += 1

                    logging.error("[%s]: Reconnecting failed. Retrying in 5 seconds." % self._log_tag)
                    time.sleep(5)

                continue

            # Check if the time of the data last received lies too far in the
            # past => send ping to check connection
            utc_timestamp = int(time.time())
            if (utc_timestamp - self._connection.last_communication) > self._ping_interval:
                logging.debug("[%s]: Ping interval exceeded." % self._log_tag)

                # check if PING failed
                promise = self._connection.send_ping()  # type: Promise
                promise.is_finished(blocking=True)
                if not promise.was_successful():
                    logging.error("[%s]: Connection to server has died." % self._log_tag)

                    # Reconnect to the server
                    while True:

                        # check if 5 unsuccessful attempts are made to connect
                        # to the server and if smtp alert is activated
                        # => send eMail alert
                        if self._smtp_alert is not None and (self._connection_retries % 5) == 0:
                            self._smtp_alert.sendCommunicationAlert(self._connection_retries)

                        # try to connect to the server
                        if self._connection.reconnect():
                            # if smtp alert is activated
                            # => send email that communication
                            # problems are solved
                            if self._smtp_alert is not None:
                                self._smtp_alert.sendCommunicationAlertClear()

                            logging.info("[%s] Reconnecting successful after %d attempts."
                                         % (self._log_tag, self._connection_retries))

                            self._connection_retries = 1
                            break

                        self._connection_retries += 1

                        logging.error("[%s]: Reconnecting failed. Retrying in 5 seconds." % self._log_tag)
                        time.sleep(5)

    def exit(self):
        """
        Sets the exit flag to shut down the thread.
        """
        self._exit_flag = True