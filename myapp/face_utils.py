import cv2
import numpy as np
import os
from django.conf import settings

face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

recognizer = cv2.face.LBPHFaceRecognizer_create()
TRAINER_PATH = os.path.join(settings.MEDIA_ROOT, "trainer.yml")
DATASET_PATH = os.path.join(settings.MEDIA_ROOT, "dataset")


def train_model():
    faces = []
    labels = []

    # CHECK IF DATASET EXISTS
    if not os.path.exists(DATASET_PATH):
        return
    
    for label in os.listdir(DATASET_PATH):
        label_path = os.path.join(DATASET_PATH, label)
        
        # SKIP IF NOT A DIRECTORY
        if not os.path.isdir(label_path):
            continue

        for img in os.listdir(label_path):
            img_path = os.path.join(label_path, img)

            image = cv2.imread(img_path)
            if image is None:  # SKIP CORRUPTED IMAGES
                continue
                
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            detected_faces = face_cascade.detectMultiScale(
                gray, scaleFactor=1.3, minNeighbors=5
            )

            for (x, y, w, h) in detected_faces:
                face = gray[y:y+h, x:x+w]
                face = cv2.resize(face, (200, 200))

                faces.append(face)
                labels.append(int(label))

    if len(faces) > 0:
        recognizer.train(faces, np.array(labels))
        recognizer.save(TRAINER_PATH)
    else:
        # DELETE TRAINER IF NO DATA
        if os.path.exists(TRAINER_PATH):
            os.remove(TRAINER_PATH)


def recognize_face(image_file):
    if not os.path.exists(TRAINER_PATH):
        print("❌ Trainer model not found!")
        return None, None

    recognizer.read(TRAINER_PATH)

    image = cv2.imread(image_file)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    faces = face_cascade.detectMultiScale(
        gray, scaleFactor=1.3, minNeighbors=5
    )

    if len(faces) == 0:
        print("❌ No face detected in uploaded image")
        return "no_face", None

    # Take largest face
    (x, y, w, h) = max(faces, key=lambda f: f[2] * f[3])
    face = gray[y:y+h, x:x+w]
    face = cv2.resize(face, (200, 200))

    label, confidence = recognizer.predict(face)
    
    print(f"✅ Predicted Label: {label}, Confidence: {confidence}")

    # RELAXED THRESHOLD
    if confidence < 95:
        return label, confidence

    return None, confidence