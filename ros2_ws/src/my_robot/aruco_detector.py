import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from geometry_msgs.msg import PoseArray, Pose
from cv_bridge import CvBridge
import cv2
import numpy as np

class ArucoDetector(Node):
    def __init__(self):
        super().__init__('aruco_detector')
        self.bridge = CvBridge()

        self.sub = self.create_subscription(
            Image,
            '/camera_sensor/image_raw',
            self.image_callback,
            10
        )

        self.pose_pub = self.create_publisher(PoseArray, '/aruco/poses', 10)
        self.image_pub = self.create_publisher(Image, '/aruco/image', 10)

        self.aruco_dict = cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_50)
        
        # Very relaxed parameters
        self.aruco_params = cv2.aruco.DetectorParameters_create()
        self.aruco_params.adaptiveThreshWinSizeMin = 3
        self.aruco_params.adaptiveThreshWinSizeMax = 100
        self.aruco_params.adaptiveThreshWinSizeStep = 5
        self.aruco_params.adaptiveThreshConstant = 1
        self.aruco_params.minMarkerPerimeterRate = 0.01
        self.aruco_params.maxMarkerPerimeterRate = 4.0
        self.aruco_params.polygonalApproxAccuracyRate = 0.1
        self.aruco_params.minCornerDistanceRate = 0.01
        self.aruco_params.minDistanceToBorder = 1
        self.aruco_params.errorCorrectionRate = 1.0

        self.camera_matrix = np.array([
            [554.25, 0, 320.0],
            [0, 554.25, 240.0],
            [0, 0, 1.0]
        ], dtype=np.float32)
        self.dist_coeffs = np.zeros((4, 1))

        self.get_logger().info('ArUco Detector Node started!')

    def image_callback(self, msg):
        frame = self.bridge.imgmsg_to_cv2(msg, 'bgr8')
        
        # Preprocess - brighten and increase contrast
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frame_eq = cv2.equalizeHist(frame_gray)
        frame_bright = cv2.cvtColor(frame_eq, cv2.COLOR_GRAY2BGR)

        pose_array = PoseArray()
        pose_array.header.stamp = self.get_clock().now().to_msg()
        pose_array.header.frame_id = 'camera_link'

        # Try on both original and brightened frame
        for f in [frame, frame_bright]:
            corners, ids, _ = cv2.aruco.detectMarkers(
                f, self.aruco_dict, parameters=self.aruco_params
            )
            if ids is not None:
                self.get_logger().info(f'Detected markers: {ids.flatten().tolist()}')
                cv2.aruco.drawDetectedMarkers(frame, corners, ids)

                for i, corner in enumerate(corners):
                    rvec, tvec, _ = cv2.aruco.estimatePoseSingleMarkers(
                        corner, 0.2, self.camera_matrix, self.dist_coeffs
                    )
                    pose = Pose()
                    pose.position.x = float(tvec[0][0][0])
                    pose.position.y = float(tvec[0][0][1])
                    pose.position.z = float(tvec[0][0][2])
                    pose_array.poses.append(pose)
                break

        self.pose_pub.publish(pose_array)
        self.image_pub.publish(self.bridge.cv2_to_imgmsg(frame, 'bgr8'))

def main(args=None):
    rclpy.init(args=args)
    node = ArucoDetector()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
