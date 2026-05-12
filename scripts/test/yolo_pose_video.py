import cv2
import sys
from ultralytics import YOLO
import math

def euclidean(p1, p2):
    return math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)

def classify_posture(keypoints):
    try:
        l_shoulder = keypoints[5]
        r_shoulder = keypoints[6]
        l_hip = keypoints[11]
        r_hip = keypoints[12]
        l_ankle = keypoints[15]
        r_ankle = keypoints[16]
        nose = keypoints[0]

        shoulder_mid = [(l_shoulder[0] + r_shoulder[0]) / 2, (l_shoulder[1] + r_shoulder[1]) / 2]
        hip_mid = [(l_hip[0] + r_hip[0]) / 2, (l_hip[1] + r_hip[1]) / 2]
        ankle_mid = [(l_ankle[0] + r_ankle[0]) / 2, (l_ankle[1] + r_ankle[1]) / 2]

        # Distances
        torso_len = euclidean(shoulder_mid, hip_mid)
        full_body_height = euclidean(nose, ankle_mid)
        vertical_leg = (abs(l_hip[1] - l_ankle[1]) + abs(r_hip[1] - r_ankle[1])) / 2
        total_height = torso_len + vertical_leg
        leg_ratio = vertical_leg / total_height
        compression = torso_len / full_body_height

        # Torso angle
        dx = hip_mid[0] - shoulder_mid[0]
        dy = hip_mid[1] - shoulder_mid[1]
        torso_angle = abs(math.degrees(math.atan2(dy, dx)))

        # Posture Classification
        if 60 <= torso_angle < 100:
            return "Standing"
        elif 100 <= torso_angle < 130:
            return "Sitting"
        elif torso_angle >= 130:
            return "Lying/Fallen"
        else:
            return "Unknown"
    except:
        return "Unknown"


# === CLI Input Handling ===
if len(sys.argv) != 3:
    print("Usage: python yolo_pose_video.py <video_path> <model_path>")
    sys.exit(1)

video_path = sys.argv[1]
model_path = sys.argv[2]
model = YOLO(model_path)
cap = cv2.VideoCapture(video_path)

if not cap.isOpened():
    print("Error: Cannot open video.")
    sys.exit(1)

width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps = cap.get(cv2.CAP_PROP_FPS)
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter("D:\HARSHIT RAJ\Projects\posevision-project\assets\videos\output_pose.mp4", fourcc, fps, (width, height))

while True:
    ret, frame = cap.read()
    if not ret:
        break

    results = model(frame, verbose=False)
    annotated = frame.copy()

    for kp in results[0].keypoints:
        keypoints = kp.xy[0].tolist()
        for i, (x, y) in enumerate(keypoints):
            x, y = int(x), int(y)
            cv2.circle(annotated, (x, y), 5, (0, 255, 0), -1)
        posture = classify_posture(keypoints)
        try:
            x_label, y_label = int(keypoints[11][0]), int(keypoints[11][1]) - 10
        except:
            x_label, y_label = 20, 30
        cv2.putText(annotated, posture, (x_label, y_label), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 0), 2)

    out.write(annotated)
    cv2.imshow("Video Pose + Posture", annotated)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
out.release()
cv2.destroyAllWindows()
