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

        # New thresholds
        print(f"Torso angle: {torso_angle} | leg ratio: {leg_ratio} | compression: {compression}\n")
        if torso_angle < 100 and leg_ratio > 0.45 and compression < 0.40:
            return "Standing"
        elif compression >= 0.40 and torso_angle > 100:
            return "Sitting"
        else:
            return "Lying/Fallen"
    except:
        return "Unknown"