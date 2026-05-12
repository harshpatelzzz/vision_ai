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

        # Torso height (shoulder to hip)
        torso = (euclidean(l_shoulder, l_hip) + euclidean(r_shoulder, r_hip)) / 2

        # Vertical distance hip to ankle
        vertical_leg = (abs(l_hip[1] - l_ankle[1]) + abs(r_hip[1] - r_ankle[1])) / 2

        # Total height estimate
        total_height = torso + vertical_leg
        leg_ratio = vertical_leg / total_height

        if leg_ratio > 0.5 and torso > 30:
            return "Standing"
        elif leg_ratio > 0.25:
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
