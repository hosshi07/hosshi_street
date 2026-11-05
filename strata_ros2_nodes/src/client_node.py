#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
strata communication sample :: CLIENT side (ROS 2 / rclpy)

Role of this node
  A. Topic publisher   : "strata/cmd"     (std_msgs/String)   -> server's subscriber
  B. Topic subscriber  : "strata/status"  (std_msgs/String)   <- server's publisher
  C. Service (action) client: performs a request/response round trip on "strata/calc"
       request  : service_msgs/ServiceRequest    float64_values = [a, b]
       response : service_msgs/ServiceResponse   float64_values = [a+b, a-b, a*b]
       (rclpy has no service-client helper, so the client side is built manually
         from a request publisher + a response subscription, matched by header
         transaction_id.)

Run (needs a ROS 2 environment; not verified here)
    ros2 run strata_ros2_nodes client_node.py --count 5 --a 3 --b 4

Import note
  Imports use the Jazzy-and-later style "from <pkg> import <Type>".
  On Humble/Galaxy use the legacy style "from <pkg>.msg import <Type>".
"""

import argparse
import time
import uuid

import rclpy
from rclpy.node import Node

from std_msgs import String
from service_msgs import ServiceRequest, ServiceResponse, ServiceValue

TOPIC_CMD = "strata/cmd"
TOPIC_STATUS = "strata/status"
SERVICE_NAME = "strata/calc"
REQ_TOPIC = SERVICE_NAME + "/request"
RESP_TOPIC = SERVICE_NAME + "/response"

QOS = 10
RESP_CACHE_MAX = 16          # keep at most this many pending responses
CMD_TEXTS = ("ping", "add 1 2", "status")


class StrataClient(Node):
    """Topic publisher + topic subscriber + service client."""

    def __init__(self):
        # Jazzy+ may accept no argument here; see server_node.py for the note.
        super().__init__("strata_client")

        self._seq = 0
        self._responses = {}     # transaction_id -> ServiceResponse
        self._cmd_index = 0

        # --- A. topic publisher ---------------------------------------------
        self.pub_cmd = self.create_publisher(String, TOPIC_CMD, QOS)

        # --- B. topic subscription ------------------------------------------
        self.create_subscription(String, TOPIC_STATUS, self.on_status, QOS)

        # --- C. service client side: request pub + response subscription ----
        self.req_pub = self.create_publisher(ServiceRequest, REQ_TOPIC, QOS)
        self.create_subscription(ServiceResponse, RESP_TOPIC, self.on_response, QOS)

        self.get_logger().info(
            "strata_client ready: cmd=%s status=%s service=%s"
            % (TOPIC_CMD, TOPIC_STATUS, SERVICE_NAME)
        )

    # ---------------------------------------------------------------------- #
    #  B. topic subscription handler
    # ---------------------------------------------------------------------- #
    def on_status(self, msg: String) -> None:
        """Print whatever the server published on the status topic."""
        self.get_logger().info("[status] %s" % msg.data)

    # ---------------------------------------------------------------------- #
    #  A. topic publisher helper
    # ---------------------------------------------------------------------- #
    def send_command(self, text: str) -> None:
        self.pub_cmd.publish(String(data=text))
        self.get_logger().info("[cmd] sent -> %s" % text)

    # ---------------------------------------------------------------------- #
    #  C-1. response handler: cache by transaction_id
    # ---------------------------------------------------------------------- #
    def on_response(self, resp: ServiceResponse) -> None:
        """Store a response under its transaction_id so call_calc() can pick it up."""
        tid = resp.header.transaction_id
        if not tid:
            self.get_logger().warning("response arrived without transaction_id")
            return
        self._responses[tid] = resp
        while len(self._responses) > RESP_CACHE_MAX:
            self._responses.pop(next(iter(self._responses)))

    # ---------------------------------------------------------------------- #
    #  C-2. service call: publish request, wait for the matching response
    # ---------------------------------------------------------------------- #
    def call_calc(self, a: float, b: float, timeout_sec: float = 2.0):
        """Send one service request and return the ServiceResponse, or None on timeout."""
        tid = str(uuid.uuid4())

        request = ServiceRequest()
        request.header.transaction_id = tid
        request.header.source_uri = self.fully_qualified_name()
        request.header.target_uri = "/" + SERVICE_NAME
        request.header.sequence_number = self._seq
        request.header.request_id = tid
        self._seq += 1

        payload = ServiceValue()
        payload.float64_values = [float(a), float(b)]
        request.in_ = payload

        self.req_pub.publish(request)

        # Spin the node so the response callback gets invoked; match on tid.
        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.02)
            if tid in self._responses:
                return self._responses.pop(tid)

        self.get_logger().warning(
            "no response from service %s within %.1fs" % (SERVICE_NAME, timeout_sec)
        )
        return None

    @staticmethod
    def unpack_calc_response(resp: ServiceResponse):
        """Turn ServiceResponse into a list of (op_name, value) pairs."""
        out = []
        for value in resp.from_server:
            for name, num in zip(value.string_values, value.float64_values):
                out.append((name, num))
            if not value.string_values:
                out.extend(("", v) for v in value.float64_values)
        return out


def main(args=None):
    parser = argparse.ArgumentParser(description="strata client node")
    parser.add_argument("--count", type=int, default=0,
                        help="number of rounds; 0 = loop forever")
    parser.add_argument("--a", type=float, default=1.5, help="first calc operand")
    parser.add_argument("--b", type=float, default=2.5, help="second calc operand")
    parser.add_argument("--timeout", type=float, default=2.0,
                        help="service response timeout [s]")
    opts, _unknown = parser.parse_known_args(args)

    rclpy.init(args=args)
    node = StrataClient()
    step = 0
    try:
        while opts.count == 0 or step < opts.count:
            # A. push a command to the server over the topic
            node.send_command(CMD_TEXTS[node._cmd_index % len(CMD_TEXTS)])
            node._cmd_index += 1

            # C. call the service and process what comes back
            resp = node.call_calc(opts.a + step, opts.b, opts.timeout)
            if resp is not None:
                for name, num in node.unpack_calc_response(resp):
                    node.get_logger().info("[service] %s = %g" % (name, num))

            # B. give the status subscription a window to report in
            rclpy.spin_once(node, timeout_sec=1.0)
            step += 1
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_nodes()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
