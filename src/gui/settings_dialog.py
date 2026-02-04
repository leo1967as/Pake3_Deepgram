from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QLineEdit, QComboBox, QSpinBox, QCheckBox, 
                               QPushButton, QGroupBox, QMessageBox)
from PySide6.QtCore import Qt
from config_manager import config

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ General Settings")
        self.resize(400, 550)
        
        # Apply Dark Theme explicitly
        self.setStyleSheet("""
            QDialog { background-color: #1a1a1f; color: #e0e0e0; }
            QLabel { color: #e0e0e0; font-size: 12px; }
            QGroupBox { border: 1px solid #333; margin-top: 6px; padding-top: 10px; color: #a0a0b0; font-weight: bold; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px; }
            QLineEdit, QSpinBox, QComboBox { 
                background-color: #2a2a3a; 
                color: #ffffff; 
                border: 1px solid #3a3a4a; 
                padding: 5px; 
                border-radius: 4px; 
            }
            QCheckBox { color: #e0e0e0; }
            QPushButton { 
                background-color: #3b82f6; 
                color: white; 
                border: none; 
                padding: 8px 16px; 
                border-radius: 4px; 
                font-weight: bold;
            }
            QPushButton:hover { background-color: #2563eb; }
        """)
        
        layout = QVBoxLayout()
        
        # --- Group 1: Cost Management ---
        cost_group = QGroupBox("💰 Cost Saver (Features)")
        cost_layout = QVBoxLayout()
        
        self.cb_enable_translation = QCheckBox("Enable Thai Translation")
        self.cb_enable_translation.setToolTip("Uncheck to DISABLE translation API calls (Saves money)")
        
        self.cb_enable_analysis = QCheckBox("Enable Market Analysis")
        self.cb_enable_analysis.setToolTip("Uncheck to DISABLE sentiment analysis")
        
        cost_layout.addWidget(self.cb_enable_translation)
        cost_layout.addWidget(self.cb_enable_analysis)
        cost_group.setLayout(cost_layout)
        layout.addWidget(cost_group)
        
        # --- Group 2: AI Models ---
        model_group = QGroupBox("🤖 AI Model Selection")
        model_layout = QVBoxLayout()
        
        # Available models list (hardcoded for now, could be fetched ideally)
        self.available_models = [
            "google/gemini-2.5-flash-lite",
            "google/gemini-2.5-flash",
            "google/gemini-2.0-flash-001",
            "google/gemini-3-flash-preview",
            "google/gemini-3-pro-preview"
        ]
        
        # Translate Model
        model_layout.addWidget(QLabel("Translation Model:"))
        self.combo_translate = QComboBox()
        self.combo_translate.addItems(self.available_models)
        self.combo_translate.setEditable(True) # Allow custom typing
        model_layout.addWidget(self.combo_translate)

        # Analysis Model
        model_layout.addWidget(QLabel("Analysis Model:"))
        self.combo_analysis = QComboBox()
        self.combo_analysis.addItems(self.available_models)
        self.combo_analysis.setEditable(True)
        model_layout.addWidget(self.combo_analysis)
        
        model_group.setLayout(model_layout)
        layout.addWidget(model_group)

        # --- Group 3: Input Sources ---
        src_group = QGroupBox("🎧 Input Sources")
        src_layout = QVBoxLayout()
        
        # Target Media URL
        src_layout.addWidget(QLabel("Target Media URL (YouTube/Live):"))
        self.line_media_url = QLineEdit()
        self.line_media_url.setPlaceholderText("https://www.youtube.com/watch?v=...")
        src_layout.addWidget(self.line_media_url)

        # Deepgram URL
        src_layout.addWidget(QLabel("Deepgram API Endpoint:"))
        self.line_url = QLineEdit()
        self.line_url.setPlaceholderText("wss://api.deepgram.com/v1/listen...")
        src_layout.addWidget(self.line_url)
        
        src_group.setLayout(src_layout)
        layout.addWidget(src_group)

        # --- Group 4: Limits ---
        lim_group = QGroupBox("⚡ Limits")
        lim_layout = QVBoxLayout()
        
        # Max Tokens
        lim_layout.addWidget(QLabel("Max Tokens (Summary):"))
        self.spin_token_summary = QSpinBox()
        self.spin_token_summary.setRange(256, 8192)
        self.spin_token_summary.setSingleStep(128)
        lim_layout.addWidget(self.spin_token_summary)
        
        lim_group.setLayout(lim_layout)
        layout.addWidget(lim_group)

        # --- Buttons ---
        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("Save && Apply")
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setStyleSheet("background-color: #4b5563;") # Gray for cancel
        
        self.btn_save.clicked.connect(self.save_settings)
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_save)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
        
        # Load values
        self.load_values()

    def load_values(self):
        """Populate UI from config"""
        self.cb_enable_translation.setChecked(config.get("enable_translation", True))
        self.cb_enable_analysis.setChecked(config.get("enable_analysis", True))
        
        self.combo_translate.setCurrentText(config.get("model_translate"))
        self.combo_analysis.setCurrentText(config.get("model_analysis"))
        
        self.line_media_url.setText(config.get("target_media_url", ""))
        self.line_url.setText(config.get("deepgram_ws_url", ""))
        self.spin_token_summary.setValue(config.get("max_tokens_summary", 4096))

    def save_settings(self):
        """Save UI to config"""
        config.set("enable_translation", self.cb_enable_translation.isChecked())
        config.set("enable_analysis", self.cb_enable_analysis.isChecked())
        
        config.set("model_translate", self.combo_translate.currentText())
        config.set("model_analysis", self.combo_analysis.currentText())
        
        config.set("target_media_url", self.line_media_url.text().strip())
        config.set("deepgram_ws_url", self.line_url.text().strip())
        config.set("max_tokens_summary", self.spin_token_summary.value())
        
        QMessageBox.information(self, "Saved", "Settings saved successfully!\nSome changes may require restart to take effect.")
        self.accept()
