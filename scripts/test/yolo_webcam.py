from ultralytics import YOLO
import cv2

# Load pre-trained pose model
model = YOLO("yolov8n-pose.pt")

# Open webcam (0 = default cam)
cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Predict pose on the current frame
    results = model.predict(frame, conf=0.5, verbose=False)

    # Render keypoints and bounding boxes on the frame
    annotated_frame = results[0].plot()

    # Display the frame
    cv2.imshow("YOLOv8 Pose Estimation", annotated_frame)

    # Exit on pressing 'q'
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Release webcam and close windows
cap.release()
cv2.destroyAllWindows()
