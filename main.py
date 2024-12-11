import cv2
import numpy as np
import tensorflow as tf
import mediapipe as mp
import sys
import subprocess
from tensorflow.keras.applications import ResNet50
from tensorflow.keras.layers import Dense, GlobalAveragePooling2D, Dropout
from tensorflow.keras.models import Model, load_model
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.utils import to_categorical
from sklearn.model_selection import train_test_split
import matplotlib.pyplot as plt
import pyautogui
from tensorflow.keras.applications import EfficientNetB0
from tensorflow.keras.applications import MobileNetV2
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QWidget, QLineEdit, QMessageBox, 
    QDialog, QFormLayout, QSpinBox, QDoubleSpinBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QImage, QPixmap
import logging
import win32gui
import win32com.client
import json

import os 
pyautogui.FAILSAFE = True  # Enable failsafe
pyautogui.PAUSE = 0.1  # Add a small pause between actions

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SystemCallConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gesture System Call Configuration")
        self.setModal(True)
        self.resize(500, 400)

        # Expanded system calls with more options
        self.system_calls = {
            0: "Open Notepad",
            1: "Open File Explorer", 
            2: "Open Calculator",
            3: "Zoom In",
            4: "Zoom Out", 
            5: "Scroll Up",
            6: "Scroll Down",
            7: "Open Browser",
            8: "Volume Up",
            9: "Volume Down",
            10: "Custom Command"
        }

        # Configuration file path
        self.config_path = "gesture_system_call_mapping.json"
        self.custom_commands = {}  # Store custom commands

        # Load existing configuration
        self.current_mapping = self.load_configuration()
        self.custom_commands = self.load_custom_commands()

        # Create main layout
        main_layout = QVBoxLayout()

        # Gesture Mapping Group
        gesture_group = QGroupBox("Gesture to System Call Mapping")
        gesture_layout = QVBoxLayout()

        # Create gesture mapping controls
        self.gesture_combos = {}
        self.custom_command_edits = {}

        for gesture_id in range(NUM_CLASSES):
            h_layout = QHBoxLayout()
            
            label = QLabel(f"Gesture {gesture_id}:")
            combo = QComboBox()
            combo.addItems(list(self.system_calls.values()))
            
            # Custom command input
            custom_cmd_edit = QLineEdit()
            custom_cmd_edit.setPlaceholderText("Enter custom command")
            custom_cmd_edit.setVisible(False)
            
            # Set current mapping if exists
            if str(gesture_id) in self.current_mapping:
                current_call = self.current_mapping[str(gesture_id)]
                combo.setCurrentText(self.system_calls.get(current_call, "Open Notepad"))
                
                # If it's a custom command, show the edit box
                if current_call == len(self.system_calls) - 1:  # Last index is "Custom Command"
                    custom_cmd_edit.setVisible(True)
                    custom_cmd_edit.setText(self.custom_commands.get(str(gesture_id), ""))
            
            # Connect combo box to show/hide custom command input
            combo.currentTextChanged.connect(
                lambda text, edit=custom_cmd_edit: 
                edit.setVisible(text == "Custom Command")
            )
            
            h_layout.addWidget(label)
            h_layout.addWidget(combo)
            h_layout.addWidget(custom_cmd_edit)
            
            gesture_layout.addLayout(h_layout)
            
            # Store combo box and custom command edit in dictionaries
            self.gesture_combos[gesture_id] = combo
            self.custom_command_edits[gesture_id] = custom_cmd_edit

        gesture_group.setLayout(gesture_layout)
        main_layout.addWidget(gesture_group)

        # Buttons
        button_layout = QHBoxLayout()
        save_btn = QPushButton("Save Configuration")
        save_btn.clicked.connect(self.save_configuration)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

    def load_configuration(self):
        """Load existing configuration from file."""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            QMessageBox.warning(self, "Configuration Error", f"Failed to load configuration: {e}")
        return {}

    def load_custom_commands(self):
        """Load custom commands from a separate JSON file."""
        custom_commands_path = "custom_commands.json"
        try:
            if os.path.exists(custom_commands_path):
                with open(custom_commands_path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            QMessageBox.warning(self, "Custom Commands Error", f"Failed to load custom commands: {e}")
        return {}

    def save_configuration(self):
        """Save current configuration to file."""
        new_mapping = {}
        custom_commands = {}

        for gesture_id, combo in self.gesture_combos.items():
            selected_call = combo.currentText()
            
            # Find the key (system call ID) for the selected call
            system_call_id = next(
                key for key, value in self.system_calls.items() 
                if value == selected_call
            )
            new_mapping[str(gesture_id)] = system_call_id

            # Handle custom command if selected
            if selected_call == "Custom Command":
                custom_cmd = self.custom_command_edits[gesture_id].text().strip()
                if custom_cmd:
                    custom_commands[str(gesture_id)] = custom_cmd
                else:
                    QMessageBox.warning(
                        self, 
                        "Custom Command Error", 
                        f"No command specified for Gesture {gesture_id}"
                    )
                    return

        try:
            # Save system call mapping
            with open(self.config_path, 'w') as f:
                json.dump(new_mapping, f)
            
            # Save custom commands if any
            if custom_commands:
                with open("custom_commands.json", 'w') as f:
                    json.dump(custom_commands, f)
            
            # Update SystemCallManager's mapping
            self._update_system_call_manager(new_mapping, custom_commands)
            
            QMessageBox.information(
                self, 
                "Configuration", 
                "Gesture system call mapping saved successfully!"
            )
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save configuration: {e}")

    def _update_system_call_manager(self, mapping, custom_commands):
        """Update SystemCallManager with new mappings and custom commands."""
        def execute_custom_command(cmd):
            def _run():
                try:
                    subprocess.Popen(cmd, shell=True)
                except Exception as e:
                    print(f"Error executing custom command: {e}")
            return _run

        SystemCallManager.SYSTEM_CALLS = SystemCallManager.DEFAULT_SYSTEM_CALLS.copy()
        SystemCallManager.SYSTEM_CALLS.update({
            int(k): (
                execute_custom_command(custom_commands.get(str(k))) 
                if k in mapping and mapping[k] == len(self.system_calls) - 1 
                else SystemCallManager._get_system_call_function(
                    SystemCallManager.system_calls[mapping[k]]
                )
            ) for k in mapping
        })

class HandDetector:
    def __init__(self, max_hands=1, detection_confidence=0.7, tracking_confidence=0.7):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            max_num_hands=max_hands,
            min_detection_confidence=detection_confidence,
            min_tracking_confidence=tracking_confidence
        )
        self.mp_draw = mp.solutions.drawing_utils
        
    def find_hands(self, frame, draw=True):
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(frame_rgb)
        
        landmarks = []
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                if draw:
                    self.mp_draw.draw_landmarks(
                        frame,
                        hand_landmarks,
                        self.mp_hands.HAND_CONNECTIONS
                    )
                
                points = []
                for lm in hand_landmarks.landmark:
                    h, w, _ = frame.shape
                    points.append({
                        'x': int(lm.x * w),
                        'y': int(lm.y * h),
                        'z': lm.z
                    })
                landmarks.append(points)
        
        return frame, landmarks


class SystemCallConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gesture System Call Configuration")
        self.setModal(True)
        self.resize(500, 400)

        # Expanded system calls with more options
        self.system_calls = {
            0: "Open Notepad",
            1: "Open File Explorer", 
            2: "Open Calculator",
            3: "Zoom In",
            4: "Zoom Out", 
            5: "Scroll Up",
            6: "Scroll Down",
            7: "Open Browser",
            8: "Volume Up",
            9: "Volume Down",
            10: "Custom Command"
        }

        # Configuration file path
        self.config_path = "gesture_system_call_mapping.json"
        self.custom_commands = {}  # Store custom commands

        # Load existing configuration
        self.current_mapping = self.load_configuration()
        self.custom_commands = self.load_custom_commands()

        # Create main layout
        main_layout = QVBoxLayout()

        # Gesture Mapping Group
        gesture_group = QGroupBox("Gesture to System Call Mapping")
        gesture_layout = QVBoxLayout()

        # Create gesture mapping controls
        self.gesture_combos = {}
        self.custom_command_edits = {}

        for gesture_id in range(NUM_CLASSES):
            h_layout = QHBoxLayout()
            
            label = QLabel(f"Gesture {gesture_id}:")
            combo = QComboBox()
            combo.addItems(list(self.system_calls.values()))
            
            # Custom command input
            custom_cmd_edit = QLineEdit()
            custom_cmd_edit.setPlaceholderText("Enter custom command")
            custom_cmd_edit.setVisible(False)
            
            # Set current mapping if exists
            if str(gesture_id) in self.current_mapping:
                current_call = self.current_mapping[str(gesture_id)]
                combo.setCurrentText(self.system_calls.get(current_call, "Open Notepad"))
                
                # If it's a custom command, show the edit box
                if current_call == len(self.system_calls) - 1:  # Last index is "Custom Command"
                    custom_cmd_edit.setVisible(True)
                    custom_cmd_edit.setText(self.custom_commands.get(str(gesture_id), ""))
            
            # Connect combo box to show/hide custom command input
            combo.currentTextChanged.connect(
                lambda text, edit=custom_cmd_edit: 
                edit.setVisible(text == "Custom Command")
            )
            
            h_layout.addWidget(label)
            h_layout.addWidget(combo)
            h_layout.addWidget(custom_cmd_edit)
            
            gesture_layout.addLayout(h_layout)
            
            # Store combo box and custom command edit in dictionaries
            self.gesture_combos[gesture_id] = combo
            self.custom_command_edits[gesture_id] = custom_cmd_edit

        gesture_group.setLayout(gesture_layout)
        main_layout.addWidget(gesture_group)

        # Buttons
        button_layout = QHBoxLayout()
        save_btn = QPushButton("Save Configuration")
        save_btn.clicked.connect(self.save_configuration)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

    def load_configuration(self):
        """Load existing configuration from file."""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            QMessageBox.warning(self, "Configuration Error", f"Failed to load configuration: {e}")
        return {}

    def load_custom_commands(self):
        """Load custom commands from a separate JSON file."""
        custom_commands_path = "custom_commands.json"
        try:
            if os.path.exists(custom_commands_path):
                with open(custom_commands_path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            QMessageBox.warning(self, "Custom Commands Error", f"Failed to load custom commands: {e}")
        return {}

    def save_configuration(self):
        """Save current configuration to file."""
        new_mapping = {}
        custom_commands = {}

        for gesture_id, combo in self.gesture_combos.items():
            selected_call = combo.currentText()
            
            # Find the key (system call ID) for the selected call
            system_call_id = next(
                key for key, value in self.system_calls.items() 
                if value == selected_call
            )
            new_mapping[str(gesture_id)] = system_call_id

            # Handle custom command if selected
            if selected_call == "Custom Command":
                custom_cmd = self.custom_command_edits[gesture_id].text().strip()
                if custom_cmd:
                    custom_commands[str(gesture_id)] = custom_cmd
                else:
                    QMessageBox.warning(
                        self, 
                        "Custom Command Error", 
                        f"No command specified for Gesture {gesture_id}"
                    )
                    return

        try:
            # Save system call mapping
            with open(self.config_path, 'w') as f:
                json.dump(new_mapping, f)
            
            # Save custom commands if any
            if custom_commands:
                with open("custom_commands.json", 'w') as f:
                    json.dump(custom_commands, f)
            
            # Update SystemCallManager's mapping
            self._update_system_call_manager(new_mapping, custom_commands)
            
            QMessageBox.information(
                self, 
                "Configuration", 
                "Gesture system call mapping saved successfully!"
            )
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save configuration: {e}")

    def _update_system_call_manager(self, mapping, custom_commands):
        """Update SystemCallManager with new mappings and custom commands."""
        def execute_custom_command(cmd):
            def _run():
                try:
                    subprocess.Popen(cmd, shell=True)
                except Exception as e:
                    print(f"Error executing custom command: {e}")
            return _run

        SystemCallManager.SYSTEM_CALLS = SystemCallManager.DEFAULT_SYSTEM_CALLS.copy()
        SystemCallManager.SYSTEM_CALLS.update({
            int(k): (
                execute_custom_command(custom_commands.get(str(k))) 
                if k in mapping and mapping[k] == len(self.system_calls) - 1 
                else SystemCallManager._get_system_call_function(
                    SystemCallManager.system_calls[mapping[k]]
                )
            ) for k in mapping
        })
class SystemCallManager:
    system_calls = {
        0: "Open Notepad",
        1: "Open File Explorer", 
        2: "Open Calculator",
        3: "Zoom In",
        4: "Zoom Out", 
        5: "Scroll Up",
        6: "Scroll Down"
    }

    DEFAULT_SYSTEM_CALLS = {
        0: lambda: subprocess.Popen('notepad.exe'),
        1: lambda: subprocess.Popen('explorer.exe'),
        2: lambda: subprocess.Popen('calc.exe'),
        3: lambda: SystemCallManager._windows_zoom_in(),
        4: lambda: SystemCallManager._windows_zoom_out(),
        5: lambda: pyautogui.scroll(100),
        6: lambda: pyautogui.scroll(-100)
    }

    SYSTEM_CALLS = DEFAULT_SYSTEM_CALLS.copy()


    @classmethod
    def _windows_zoom_in(cls):
        try:
            # Try multiple zoom-in methods
            pyautogui.hotkey('ctrl', '+')  # First method
        except Exception as e:
            try:
                # Alternative method using SendKeys
                shell = win32com.client.Dispatch("WScript.Shell")
                shell.SendKeys("^{ADD}")  # Ctrl + +
            except Exception as inner_e:
                logger.error(f"Zoom in failed: {e}, {inner_e}")
                raise

    @classmethod
    def _windows_zoom_out(cls):
        try:
            # Try multiple zoom-out methods
            pyautogui.hotkey('ctrl', '-')  # First method
        except Exception as e:
            try:
                # Alternative method using SendKeys
                shell = win32com.client.Dispatch("WScript.Shell")
                shell.SendKeys("^{SUBTRACT}")  # Ctrl + -
            except Exception as inner_e:
                logger.error(f"Zoom out failed: {e}, {inner_e}")
                raise

    @classmethod
    def execute_system_call(cls, gesture_id):
        print(f"Gesture ID: {gesture_id}")
        logger.info(f"Attempting to execute system call for gesture {gesture_id}")
        try:
            if gesture_id in cls.SYSTEM_CALLS:
                print(f"Found system call for gesture {gesture_id}")
                cls.SYSTEM_CALLS[gesture_id]()
                logger.info(f"Successfully executed system call for gesture {gesture_id}")
            else:
                logger.warning(f"No system call defined for gesture {gesture_id}")
                print(f"No system call defined for gesture {gesture_id}")
        except Exception as e:
            logger.error(f"Error executing system call for gesture {gesture_id}: {e}")
            print(f"Error details: {e}")
    SYSTEM_CALLS = DEFAULT_SYSTEM_CALLS.copy()

    @classmethod
    def _get_system_call_function(cls, call_name):
        """Map system call names to their corresponding functions."""
        system_call_map = {
            "Open Notepad": lambda: subprocess.Popen('notepad.exe'),
            "Open File Explorer": lambda: subprocess.Popen('explorer.exe'),
            "Open Calculator": lambda: subprocess.Popen('calc.exe'),
            "Zoom In": lambda: SystemCallManager._windows_zoom_in(),
            "Zoom Out": lambda: SystemCallManager._windows_zoom_out(),
            "Scroll Up": lambda: pyautogui.scroll(100),
            "Scroll Down": lambda: pyautogui.scroll(-100)
        }
        return system_call_map.get(call_name, cls.DEFAULT_SYSTEM_CALLS[0])
    

class GestureRecognition:
    def __init__(self, model_path=None, num_classes=7):
        self.num_classes = num_classes
        self.model = self._build_model() if model_path is None else load_model(model_path)
        self.hand_detector = HandDetector(detection_confidence=0.7, tracking_confidence=0.7)
        self.system_call_manager = SystemCallManager()
    
    def _build_model(self):
        base_model = MobileNetV2(
            input_shape=(224, 224, 3),
            include_top=False,
            weights='imagenet'
        )
        
        # Fine-tune more layers
        base_model.trainable = True
        for layer in base_model.layers[:-20]:
            layer.trainable = False
        
        x = base_model.output
        x = GlobalAveragePooling2D()(x)
        x = Dense(1024, activation='relu', kernel_regularizer=tf.keras.regularizers.L2(l2=0.001))(x)
        x = Dropout(0.5)(x)
        predictions = Dense(NUM_CLASSES, activation='softmax')(x)
        
        model = Model(inputs=base_model.input, outputs=predictions)
        model.compile(
            optimizer=Adam(learning_rate=0.0001),
            loss='categorical_crossentropy', 
            metrics=['accuracy']
        )
        return model
    
    def preprocess_frame(self, frame):
        frame = cv2.resize(frame, (224, 224))
        frame = frame / 255.0
        frame = np.expand_dims(frame, axis=0)
        return frame
    
    def predict_gesture(self, frame):
        processed_frame = self.preprocess_frame(frame)
        predictions = self.model.predict(processed_frame, verbose=0)
        confidence = np.max(predictions[0])
        gesture_id = np.argmax(predictions[0])
        
        # Add confidence threshold to reduce false positives
        return gesture_id if confidence > 0.5 else None
        return gesture_id 

class GestureDataCollector:
    def __init__(self, output_dir="gesture_data"):
        self.output_dir = output_dir
        self.hand_detector = HandDetector()
        os.makedirs(output_dir, exist_ok=True)
    
    def collect_data(self, gesture_id, num_samples=100):
        gesture_dir = os.path.join(self.output_dir, str(gesture_id))
        os.makedirs(gesture_dir, exist_ok=True)
        
        cap = cv2.VideoCapture(0)
        count = 0
        
        while count < num_samples:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Detect hands and draw landmarks
            frame, landmarks = self.hand_detector.find_hands(frame)
            
            # Display instructions
            cv2.putText(
                frame,
                f"Samples: {count}/{num_samples}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),
                2
            )
            cv2.putText(
                frame,
                "Press SPACE to capture",
                (10, 70),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),
                2
            )
            
            cv2.imshow('Data Collection', frame)
            
            key = cv2.waitKey(1)
            if key & 0xFF == ord(' ') and landmarks:  # Only save if hand is detected
                filename = os.path.join(gesture_dir, f'gesture_{count}.jpg')
                cv2.imwrite(filename, frame)
                count += 1
                print(f"Saved frame {count}/{num_samples}")
            elif key & 0xFF == ord('q'):
                break
        
        cap.release()
        cv2.destroyAllWindows()


def prepare_dataset(data_dir):
    images = []
    labels = []
    
    for gesture_id in os.listdir(data_dir):
        gesture_path = os.path.join(data_dir, gesture_id)
        if os.path.isdir(gesture_path):
            for image_file in os.listdir(gesture_path):
                image_path = os.path.join(gesture_path, image_file)
                image = cv2.imread(image_path)
                image = cv2.resize(image, (224, 224))
                images.append(image)
                labels.append(int(gesture_id))
    
    print(f"Total images collected: {len(images)}")
    print(f"Labels distribution: {np.unique(labels, return_counts=True)}")
    
    # Normalize consistently
    X = np.array(images) / 255.0  
    
    # One-hot encode labels carefully
    y = to_categorical(np.array(labels), num_classes=NUM_CLASSES)
    
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    
    return X_train, X_test, y_train, y_test

def train_model(model, data_dir, epochs=15, batch_size=32):
    X_train, X_test, y_train, y_test = prepare_dataset(data_dir)
    
    
    # Train model
    history = model.fit(
        X_train,
        y_train,
        batch_size=batch_size,
        epochs=epochs,
        validation_data=(X_test, y_test)
    )
    
    plt.figure(figsize=(12, 4))
    
    plt.subplot(1, 2, 1)
    plt.plot(history.history['accuracy'], label='Training Accuracy')
    plt.plot(history.history['val_accuracy'], label='Validation Accuracy')
    plt.title('Model Accuracy')
    plt.xlabel('Epoch')
    plt.ylabel('Accuracy')
    plt.legend()
    
    plt.subplot(1, 2, 2)
    plt.plot(history.history['loss'], label='Training Loss')
    plt.plot(history.history['val_loss'], label='Validation Loss')
    plt.title('Model Loss')
    plt.xlabel('Epoch')
    plt.ylabel('Loss')
    plt.legend()
    
    plt.tight_layout()
    plt.savefig('training_history.png')
    
    return model

class GestureRecognitionApp(QMainWindow):
    def __init__(self, model_path, num_classes=7):
        super().__init__()
        self.setWindowTitle("Gesture System Call Application")
        self.resize(800, 600)

        # Configuration file
        self.config_path = "gesture_recognition_config.json"
        
        # Load or set default configuration
        self.load_config()

        # Initialize gesture recognition
        self.gesture_recognition = GestureRecognition(model_path, num_classes)
        
        # Setup UI
        central_widget = QWidget()
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        self.video_label = QLabel("Waiting for camera...")
        self.video_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.video_label)

        # Button layout
        button_layout = QHBoxLayout()
        
        # Recognition toggle button
        self.recognition_btn = QPushButton("Start Recognition")
        self.recognition_btn.clicked.connect(self.toggle_recognition)
        button_layout.addWidget(self.recognition_btn)

        # Training button
        self.train_btn = QPushButton("Train Model")
        self.train_btn.clicked.connect(self.open_training_dialog)
        button_layout.addWidget(self.train_btn)

        # System Call Config button
        config_btn = QPushButton("Configure System Calls")
        config_btn.clicked.connect(self.open_system_call_configuration)
        button_layout.addWidget(config_btn)

        # Model Config button
        model_config_btn = QPushButton("Model Settings")
        model_config_btn.clicked.connect(self.open_model_configuration)
        button_layout.addWidget(model_config_btn)

        main_layout.addLayout(button_layout)

        # Camera and recognition setup
        self.camera = cv2.VideoCapture(0)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        
        self.is_recognizing = False
        self.last_gesture = None
        self.cooldown_counter = 0

    def load_config(self):
        """Load configuration from file or set defaults."""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
                    self.confidence_threshold = config.get('confidence', 0.5)
                    self.gesture_cooldown = config.get('cooldown', 30)
            else:
                # Default values
                self.confidence_threshold = 0.5
                self.gesture_cooldown = 30
        except Exception as e:
            print(f"Error loading config: {e}")
            self.confidence_threshold = 0.5
            self.gesture_cooldown = 30

    def save_config(self, config):
        """Save configuration to file."""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(config, f)
            
            # Update current instance
            self.confidence_threshold = config.get('confidence', 0.5)
            self.gesture_cooldown = config.get('cooldown', 30)
        except Exception as e:
            QMessageBox.warning(self, "Configuration Error", f"Failed to save configuration: {e}")

    def open_training_dialog(self):
        """Open training configuration dialog."""
        training_dialog = TrainingConfigDialog(self)
        if training_dialog.exec_() == QDialog.Accepted:
            config = training_dialog.get_config()
            
            # Perform training
            try:
                DATA_DIR = "gesture_data"
                MODEL_PATH = "gesture_system_call_model.h5"
                
                # Collect data
                collector = GestureDataCollector(DATA_DIR)
                for gesture_id in range(NUM_CLASSES):
                    collector.collect_data(gesture_id, config['samples_per_gesture'])
                
                # Train model
                gesture_system = GestureRecognition(num_classes=NUM_CLASSES)
                trained_model = train_model(
                    gesture_system.model, 
                    DATA_DIR, 
                    epochs=config['epochs'], 
                    batch_size=config['batch_size']
                )
                trained_model.save(MODEL_PATH)
                
                # Update the current model
                self.gesture_recognition = GestureRecognition(MODEL_PATH, NUM_CLASSES)
                
                QMessageBox.information(self, "Training", "Model trained successfully!")
            except Exception as e:
                QMessageBox.warning(self, "Training Error", f"Failed to train model: {e}")

    def open_system_call_configuration(self):
        """Open system call configuration dialog."""
        config_dialog = SystemCallConfigDialog(self)
        config_dialog.exec_()

    def open_model_configuration(self):
        """Open model configuration dialog."""
        current_config = {
            'confidence': self.confidence_threshold,
            'cooldown': self.gesture_cooldown
        }
        config_dialog = ModelConfigDialog(current_config, self)
        if config_dialog.exec_() == QDialog.Accepted:
            config = config_dialog.get_config()
            self.save_config(config)

    def toggle_recognition(self):
        if not self.is_recognizing:
            self.start_recognition()
        else:
            self.stop_recognition()

    def start_recognition(self):
        self.is_recognizing = True
        self.recognition_btn.setText("Stop Recognition")
        self.timer.start(30)

    def stop_recognition(self):
        self.is_recognizing = False
        self.recognition_btn.setText("Start Recognition")
        self.timer.stop()
        self.video_label.setText("Recognition Stopped")

    def update_frame(self):
        ret, frame = self.camera.read()
        if not ret:
            return

        frame, landmarks = self.gesture_recognition.hand_detector.find_hands(frame)
        
        if landmarks and self.is_recognizing:
            # Modify prediction to use configurable confidence threshold
            gesture_id = self.gesture_recognition.predict_gesture(frame)
            
            if gesture_id is not None:
                # Display gesture ID
                cv2.putText(
                    frame,
                    f"Gesture: {gesture_id}",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 255, 0),
                    2
                )
                
                # Execute system call with cooldown
                if gesture_id != self.last_gesture:
                    self.gesture_recognition.system_call_manager.execute_system_call(gesture_id)
                    self.last_gesture = gesture_id
                    self.cooldown_counter = self.gesture_cooldown

        # Convert frame to Qt format
        rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        convert_to_qt_format = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(convert_to_qt_format)
        self.video_label.setPixmap(pixmap.scaled(self.video_label.size(), Qt.KeepAspectRatio))


class TrainingConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Training Configuration")
        self.setModal(True)
        
        layout = QFormLayout()
        
        # Samples per Gesture
        self.samples_spin = QSpinBox()
        self.samples_spin.setRange(50, 500)
        self.samples_spin.setValue(200)
        layout.addRow("Samples per Gesture:", self.samples_spin)
        
        # Number of Epochs
        self.epochs_spin = QSpinBox()
        self.epochs_spin.setRange(1, 50)
        self.epochs_spin.setValue(15)
        layout.addRow("Training Epochs:", self.epochs_spin)
        
        # Batch Size
        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setRange(8, 128)
        self.batch_size_spin.setValue(32)
        layout.addRow("Batch Size:", self.batch_size_spin)
        
        # Buttons
        button_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        
        layout.addRow(button_layout)
        self.setLayout(layout)
        
    def get_config(self):
        return {
            'samples_per_gesture': self.samples_spin.value(),
            'epochs': self.epochs_spin.value(),
            'batch_size': self.batch_size_spin.value()
        }

class ModelConfigDialog(QDialog):
    def __init__(self, current_config=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Model Configuration")
        self.setModal(True)
        
        layout = QFormLayout()
        
        # Confidence Threshold
        self.confidence_spin = QDoubleSpinBox()
        self.confidence_spin.setRange(0.1, 0.9)
        self.confidence_spin.setSingleStep(0.1)
        self.confidence_spin.setDecimals(2)
        layout.addRow("Confidence Threshold:", self.confidence_spin)
        
        # Cooldown Counter
        self.cooldown_spin = QSpinBox()
        self.cooldown_spin.setRange(1, 100)
        layout.addRow("Cooldown Frames:", self.cooldown_spin)
        
        # Load existing configuration if provided
        if current_config:
            self.confidence_spin.setValue(current_config.get('confidence', 0.5))
            self.cooldown_spin.setValue(current_config.get('cooldown', 30))
        else:
            # Default values
            self.confidence_spin.setValue(0.5)
            self.cooldown_spin.setValue(30)
        
        # Buttons
        button_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(save_btn)
        button_layout.addWidget(cancel_btn)
        
        layout.addRow(button_layout)
        self.setLayout(layout)
        
    def get_config(self):
        return {
            'confidence': self.confidence_spin.value(),
            'cooldown': self.cooldown_spin.value()
        }


NUM_CLASSES = 7
def main():
    DATA_DIR = "gesture_data"
    MODEL_PATH = "gesture_system_call_model.h5"
    NUM_CLASSES = 7

    app = QApplication(sys.argv)
    gesture_app = GestureRecognitionApp(MODEL_PATH, NUM_CLASSES)
    gesture_app.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()   