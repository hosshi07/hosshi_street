#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
strata 通信 SAMPLE :: SERVER side (ROS 2 / rclpy)

【この node の役割】
  A. Topic subscribe  : "strata/cmd"      (std_msgs/String)
  B. Topic publish    : "strata/status"   (std_msgs/String)
  C. Service (action) の server side の registration : "strata/calc"
       request  : service_msgs/ServiceRequest   float64_values = [a, b]
       response : service_msgs/ServiceResponse  float64_values = [a+b, a-b, a*b]

【How to run (in an environment with ROS 2 installed)】
    ros2 run strata_ros2_nodes server_node.py

【Note on message type imports】
  The "from <pkg> import <Type>" style from Jazzy onwards is used in this file.
  If you use Humble / Galaxy, change it to the legacy style "from <pkg>.msg import <Type>".
"""

import rclpy
from rclpy.node import Node

from std_msgs import String
from service_msgs import ServiceRequest, ServiceResponse, ServiceValue

# Topic / service names (keep in sync with the names in client_node.py)
TOPIC_CMD = "strata/cmd"
TOPIC_STATUS = "strata/status"
SERVICE_NAME = "strata/calc"
REQ_TOPIC = SERVICE_NAME + "/request"
RESP_TOPIC = SERVICE_NAME + "/response"

STATUS_QOS = 10          # queue size for publisher / subscription
CMD_QOS = 10


class StrataServer(Node):
    """Topic subscriber + topic publisher + service server."""

    def __init__(self):
        # On Jazzy+ the Node constructor may take no name argument; drop the string if so.
        super().__init__("strata_server")

        self._status_count = 0
        self._last_cmd = "-"

        # --- A. topic subscribing ---------------------------------------------
        self.create_subscription(String, TOPIC_CMD, self.on_cmd, CMD_QOS)

        # --- B. topic publishing ----------------------------------------------
        self.pub_status = self.create_publisher(String, TOPIC_STATUS, STATUS_QOS)

        # --- C. service server -----------------------------------------------
        self._create_service()

        self.get_logger().info(
            "strata_server ready: cmd=%s status=%s service=%s"
            % (TOPIC_CMD, TOPIC_STATUS, SERVICE_NAME)
        )

    # --------------------------------------------------------------------- #
    #  C-1.  topic subscription handler
    # --------------------------------------------------------------------- #
    def on_cmd(self, msg: String) -> None:
        """A command from client arrives, update the internal state, and publish the status."""
        text = msg.data.strip()
        self._last_cmd = text

        if text in ("status", "ping"):
            self.publish_status("OK: last_cmd=%s calls=%d" % (text, self._status_count))
        elif text in ("halt", "stop"):
            self.get_logger().info("halt requested by client")
            self.publish_status("HALTING")
        else:
            self.publish_status("echo: " + text)

    # --------------------------------------------------------------------- #
    #  C-2.  topic publisher helper
    # --------------------------------------------------------------------- #
    def publish_status(self, text: str) -> None:
        self._status_count += 1
        self.pub_status.publish(String(data=text))

    # --------------------------------------------------------------------- #
    #  C-3.  service server registration
    #       create_service() signature differs between distros, so both are tried
    # --------------------------------------------------------------------- #
    def _create_service(self) -> None:
        try:
            # Jazzy+ :  the message type is passed explicitly
            self.create_service(
                ServiceRequest, REQ_TOPIC, ServiceResponse, RESP_TOPIC, self.on_calc
            )
        except TypeError:
            # Humble / Galaxy : the service_msgs type is fixed internally inside rclpy
            self.create_service(REQ_TOPIC, RESP_TOPIC, self.on_calc)

    def on_calc(self, request: ServiceRequest) -> ServiceResponse:
        """Take the request, then return the response as ServiceResponse."""
        response = ServiceResponse()

        values = request.in_.float64_values
        result = ServiceValue()
        if len(values) >= 2:
            a, b = float(values[0]), float(values[1])
            result.float64_values = [a + b, a - b, a * b]
            result.string_values = ["add", "sub", "mul"]
            self.get_logger().info(
                "calc(a=%g, b=%g) -> [%g, %g, %g]" % (a, b, a + b, a - b, a * b)
            )
        else:
            result.string_values = ["bad_request: need 2 float64 values"]
            self.get_logger().warning("calc request has no float64_values")

        # echo back the header so the client can identify which response belongs to which request
        response.header.transaction_id = request.header.transaction_id
        response.header.source_uri = self.fully_qualified_name()
        response.header.target_uri = request.header.target_uri
        response.header.sequence_number = request.header.sequence_number
        response.header.request_id = request.header.request_id

        response.in_response_to = request.in_
        response.from_server = [result]
        return response


def main(args=None):
    rclpy.init(args=args)
    node = StrataServer()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_nodes()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
