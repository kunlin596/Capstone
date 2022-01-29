#!/usr/bin/env python
"""This modules implements WaypointUpdater and can be executed as a separate ROS note.
"""

# STL
import math

# ROS
import rospy
from geometry_msgs.msg import PoseStamped

# Utils
import numpy as np
from scipy.spatial.kdtree import KDTree

# Local imports
from styx_msgs.msg import Lane, Waypoint


class WaypointUpdater:
    """This class implements a waypoint updater.

    This updater takes in a road graph (set of waypoints) from the waypoint loader and the current pose
    from the simulator and figures out what should be actual waypoints to for controller to follow.

    These waypoints are published in the topic `final_waypoints`, and controller will use these information
    to control the vehicle.

    This module also subscribes the topic `traffic_waypoint` and `obstacle_waypoint` from the detection modules,
    such that the vehicle is enabled to slow down or speed up with respect to the environment.

    """

    _raw_map_waypoints = None  # Cached raw map waypoints
    _map_waypoints = None  # Cached map waypoints
    _map_waypoints_tree = None  # KDTree for map waypoints

    _pose = None  # Cached ego vehicle pose
    _frequency = None  # Publish frequency
    _num_waypoints_for_controller = None  # Number of `final_waypoints` to be published

    def __init__(self, frequency=50, num_waypoints_for_controller=200):
        if frequency is not None:
            self._frequency = frequency

        if num_waypoints_for_controller is not None:
            self._num_waypoints_for_controller = num_waypoints_for_controller

        self._initialize_node()

    def _initialize_node(self):
        """Initialize ROS communications and run the node"""

        rospy.init_node("waypoint_updater")

        # `current_pose` is the current pose of the ego vehicle from simulator,
        # `geometry_msgs/PoseStamped`.
        rospy.Subscriber("/current_pose", PoseStamped, self._pose_cb)

        # List of waypoints are for tracking purpose, and only published once.
        # They are provided by a static `.csv` file and loaded by `waypoint_loader`.
        rospy.Subscriber("/base_waypoints", Lane, self._waypoints_cb)

        # `traffic_waypoint` is from the traffic light detection node for setting the
        # appropriate quantities like velocity for the final waypoint.
        # TODO
        rospy.Subscriber("/traffic_waypoint", Lane, self._traffic_cb)

        # `obstacle_waypoint` is from the obstacle detection node.
        # TODO
        rospy.Subscriber("/obstacle_waypoint", Lane, self._obstacle_cb)

        # `final_waypoints` are published to way point follower (part of Autoware).
        # This is a subset of `/base_waypoints`. The first waypoint is the one
        # in `/base_waypoints` which is the closest to the car.
        self._final_waypoints_pub = rospy.Publisher("final_waypoints", Lane, queue_size=1)

        # TODO: Add other member variables you need below

        # Spin the node right after initialization
        self._spin()

    def _spin(self):
        """Start the node."""
        rate = rospy.Rate(self._frequency)
        while not rospy.is_shutdown():
            if self._pose and self._raw_map_waypoints:
                x = self._pose.pose.position.x
                y = self._pose.pose.position.y
                self._publish_waypoints(self._get_closest_waypoint_index(x, y))
            rate.sleep()

    def _publish_waypoints(self, nearest_waypoint_index):
        """Publish final waypoints in front of the car."""
        lane = Lane()

        lane.header = self._raw_map_waypoints.header

        start = nearest_waypoint_index
        end = nearest_waypoint_index + self._num_waypoints_for_controller
        lane.waypoints = self._raw_map_waypoints.waypoints[start:end]

        self._final_waypoints_pub.publish(lane)

    def _get_closest_waypoint_index(self, x, y):
        """Compute the nearest waypoint index from the map given x, y of another point."""
        nearest_index = -1
        point = [x, y]

        if self._map_waypoints_tree:
            _, nearest_index = self._map_waypoints_tree.query([x, y], k=1)

            nearest_point = self._map_waypoints[nearest_index]
            prev_point = self._map_waypoints[nearest_index - 1]

            direction = np.dot(nearest_point - prev_point, point - nearest_point)
            if direction > 0:
                nearest_index = (nearest_index + 1) % len(self._map_waypoints)

        return nearest_index

    def _pose_cb(self, msg):
        """Callback function for receiving ego vehicle pose from ROS topic."""
        self._pose = msg

    def _waypoints_cb(self, map_waypoints):
        """Callback function for receiving map waypoints from ROS topic.

        This function will convert the map waypoints into a KDTree for later quick searching.
        """
        self._raw_map_waypoints = map_waypoints
        if not self._map_waypoints:
            self._map_waypoints = np.asarray(
                [
                    [p.pose.pose.position.x, p.pose.pose.position.y]
                    for p in self._raw_map_waypoints.waypoints
                ]
            )
            self._map_waypoints_tree = KDTree(self._map_waypoints)

    def _traffic_cb(self, msg):
        # TODO: Callback for /traffic_waypoint message. Implement
        pass

    def _obstacle_cb(self, msg):
        # TODO: Callback for /obstacle_waypoint message. We will implement it later
        pass

    @staticmethod
    def _get_waypoint_velocity(waypoint):
        return waypoint.twist.twist.linear.x

    @staticmethod
    def _set_waypoint_velocity(waypoints, index, velocity):
        waypoints[index].twist.twist.linear.x = velocity

    def distance(self, waypoints, start, end):
        dist = 0

        def _compute_dist(a, b):
            return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2)

        for i in range(start, end + 1):
            dist += _compute_dist(
                waypoints[start].pose.pose.position, waypoints[i].pose.pose.position
            )
            start = i
        return dist


if __name__ == "__main__":
    try:
        WaypointUpdater()
    except rospy.ROSInterruptException:
        rospy.logerr("Could not start waypoint updater node.")
