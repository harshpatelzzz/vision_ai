import cv2
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

        # Center of shoulders and hips
        shoulder_mid = [(l_shoulder[0] + r_shoulder[0]) / 2,
                        (l_shoulder[1] + r_shoulder[1]) / 2]
        hip_mid = [(l_hip[0] + r_hip[0]) / 2,
                   (l_hip[1] + r_hip[1]) / 2]

        # Vertical torso length
        torso_len = euclidean(shoulder_mid, hip_mid)

        # Torso angle w.r.t horizontal axis (x-axis)
        delta_x = hip_mid[0] - shoulder_mid[0]
        delta_y = hip_mid[1] - shoulder_mid[1]
        torso_angle = abs(math.degrees(math.atan2(delta_y, delta_x)))

        # Leg extension (vertical)
        vertical_leg = (abs(l_hip[1] - l_ankle[1]) + abs(r_hip[1] - r_ankle[1])) / 2
        total_height = torso_len + vertical_leg
        leg_ratio = vertical_leg / total_height

        # Posture logic
        if torso_angle > 45 and leg_ratio > 0.45:
            return "Standing"
        elif torso_angle > 30:
            return "Sitting"
        else:
            return "Lying/Fallen"
    except:
        return "Unknown"

# Load model
model = YOLO("yolov8n-pose.pt")

# Start webcam
results = model.predict(source=0, show=False, stream=True)

for r in results:
    frame = r.orig_img.copy()

    for kp in r.keypoints:
        keypoints = kp.xy[0].tolist()

        # Draw keypoints
        for i, (x, y) in enumerate(keypoints):
            x, y = int(x), int(y)
            cv2.circle(frame, (x, y), 5, (0, 255, 0), -1)
            cv2.putText(frame, f"{i}", (x + 5, y - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)

        # Classify posture
        posture = classify_posture(keypoints)

        # Put posture label near the hips (keypoint 11)
        try:
            x_label, y_label = int(keypoints[11][0]), int(keypoints[11][1]) - 10
        except:
            x_label, y_label = 20, 30  # default if hip not found

        cv2.putText(frame, posture, (x_label, y_label),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 0), 2)

    # Show the result
    cv2.imshow("Pose Detection + Posture", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cv2.destroyAllWindows()
