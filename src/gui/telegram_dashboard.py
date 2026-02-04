from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QLineEdit, QPushButton, QGroupBox, QTableWidget, 
                               QTableWidgetItem, QTextEdit, QCheckBox, QHeaderView, QMessageBox,
                               QWidget, QSplitter, QApplication, QTabWidget)
from PySide6.QtCore import Qt
from telegram_manager import tg_manager

class ChatScannerDialog(QDialog):
    """Dialog to show fetched chats and allow adding them."""
    def __init__(self, chats, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔍 Found Chats")
        self.resize(500, 400)
        self.selected_chat = None
        
        layout = QVBoxLayout(self)
        lbl = QLabel("Select a chat to add:")
        layout.addWidget(lbl)
        
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Name", "Type", "ID"])
        self.table.setRowCount(len(chats))
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        
        for i, chat in enumerate(chats):
            self.table.setItem(i, 0, QTableWidgetItem(str(chat['name'])))
            self.table.setItem(i, 1, QTableWidgetItem(str(chat['type'])))
            self.table.setItem(i, 2, QTableWidgetItem(str(chat['id'])))
            
        layout.addWidget(self.table)
        
        btn_add = QPushButton("➕ Add Selected")
        btn_add.setStyleSheet("background-color: #22c55e; color: white; font-weight: bold; padding: 8px;")
        btn_add.clicked.connect(self.accept_selection)
        layout.addWidget(btn_add)
        
    def accept_selection(self):
        row = self.table.currentRow()
        if row >= 0:
            name = self.table.item(row, 0).text()
            cid = self.table.item(row, 2).text()
            self.selected_chat = (name, cid)
            self.accept()
        else:
            QMessageBox.warning(self, "No Selection", "Please select a row first.")

class TelegramDashboard(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📡 Telegram Newsroom Dashboard")
        self.resize(950, 600)
        self.setStyleSheet("""
            QGroupBox { font-weight: bold; border: 1px solid #333; margin-top: 6px; padding-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px; color: #aaa; }
        """)
        
        main_layout = QHBoxLayout(self)
        
        # Splitter to divide left (Config/Channels) and right (Templates/Broadcast)
        splitter = QSplitter(Qt.Horizontal)
        
        # --- LEFT PANEL: Connectivity & Channels ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # Group: Connection
        conn_group = QGroupBox("🔌 Connection")
        conn_layout = QVBoxLayout()
        self.token_input = QLineEdit()
        self.token_input.setPlaceholderText("Bot Token (123456:ABC-...)")
        self.token_input.setEchoMode(QLineEdit.Password)
        
        btn_layout_conn = QHBoxLayout()
        self.btn_save_token = QPushButton("Save")
        self.btn_save_token.clicked.connect(self.save_token)
        
        self.btn_scan = QPushButton("🔍 Scan Chats")
        self.btn_scan.setToolTip("Find chat IDs from recent bot history (Send a message to bot first!)")
        self.btn_scan.clicked.connect(self.scan_chats)
        
        btn_layout_conn.addWidget(self.btn_save_token)
        btn_layout_conn.addWidget(self.btn_scan)
        
        conn_layout.addWidget(QLabel("Bot Token:"))
        conn_layout.addWidget(self.token_input)
        conn_layout.addLayout(btn_layout_conn)
        conn_group.setLayout(conn_layout)
        left_layout.addWidget(conn_group)
        
        # Group: Channels
        chan_group = QGroupBox("📢 Channels")
        chan_layout = QVBoxLayout()
        
        self.chan_table = QTableWidget()
        self.chan_table.setColumnCount(3)
        self.chan_table.setHorizontalHeaderLabels(["Name", "Chat ID", "Action"])
        self.chan_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.chan_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        chan_layout.addWidget(self.chan_table)
        
        # Add Channel Inputs
        add_layout = QHBoxLayout()
        self.input_chan_name = QLineEdit()
        self.input_chan_name.setPlaceholderText("Name (e.g. VIP)")
        self.input_chan_id = QLineEdit()
        self.input_chan_id.setPlaceholderText("Chat ID")
        self.btn_add_chan = QPushButton("Add")
        self.btn_add_chan.clicked.connect(self.add_channel)
        
        add_layout.addWidget(self.input_chan_name)
        add_layout.addWidget(self.input_chan_id)
        add_layout.addWidget(self.btn_add_chan)
        chan_layout.addLayout(add_layout)
        
        chan_group.setLayout(chan_layout)
        left_layout.addWidget(chan_group)

        
        # --- RIGHT PANEL: Templates & Rules ---
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # Group: Automation Rules
        rule_group = QGroupBox("⚙️ Automation Rules")
        rule_layout = QHBoxLayout()
        self.cb_auto_hawk_dove = QCheckBox("Auto-Post on HAWKISH/DOVISH")
        # Tabs for Control vs Logs
        self.tabs = QTabWidget()
        right_layout.addWidget(self.tabs)
        
        # TAB 1: CONTROLS
        control_tab = QWidget()
        control_layout = QVBoxLayout(control_tab)
        
        # Automation Rules
        auto_group = QGroupBox("🤖 Automation Rules")
        auto_layout = QVBoxLayout()
        
        self.chk_auto_hawk = QCheckBox("Auto-Post if HAWKISH/DOVISH")
        self.chk_auto_all = QCheckBox("Auto-Post ALL Analysis")
        self.chk_auto_summary = QCheckBox("Auto-Post Big Picture (Session Summary)")
        
        self.chk_auto_hawk.setChecked(False)  # Defaults, actual load happening below
        self.chk_auto_summary.setStyleSheet("color: #f59e0b; font-weight: bold;")
        
        auto_layout.addWidget(self.chk_auto_hawk)
        auto_layout.addWidget(self.chk_auto_all)
        auto_layout.addWidget(self.chk_auto_summary)
        
        btn_save_rules = QPushButton("Save Rules")
        btn_save_rules.clicked.connect(self.save_rules)
        auto_layout.addWidget(btn_save_rules)
        
        auto_group.setLayout(auto_layout)
        control_layout.addWidget(auto_group)
        
        # Group: Template Editor
        templ_group = QGroupBox("📝 Message Templates")
        templ_layout = QVBoxLayout()
        
        templ_layout.addWidget(QLabel("Supported Tags: {sentiment}, {impact}, {summary}, {raw_text}"))
        self.template_edit = QTextEdit()
        self.template_edit.setPlaceholderText("Enter template here...")
        self.btn_save_template = QPushButton("Save Template")
        self.btn_save_template.clicked.connect(self.save_template)
        
        templ_layout.addWidget(self.template_edit)
        templ_layout.addWidget(self.btn_save_template)
        templ_group.setLayout(templ_layout)
        control_layout.addWidget(templ_group)
        
        # Manual Broadcast
        broad_group = QGroupBox("📢 Broadcast")
        broad_layout = QVBoxLayout()
        
        self.manual_input = QLineEdit()
        self.manual_input.setPlaceholderText("Type alert message...")
        
        btn_send = QPushButton("Send Alert")
        btn_send.setStyleSheet("background-color: #ef4444; color: white; font-weight: bold;")
        btn_send.clicked.connect(self.manual_broadcast)
        
        # Test Big Picture
        btn_test_bp = QPushButton("🧪 Test Big Picture")
        btn_test_bp.setToolTip("Send a dummy Big Picture summary to test formatting.")
        btn_test_bp.setStyleSheet("background-color: #8b5cf6; color: white;")
        btn_test_bp.clicked.connect(self.test_big_picture)
        
        broad_layout.addWidget(self.manual_input)
        broad_layout.addWidget(btn_send)
        broad_layout.addWidget(btn_test_bp)
        
        broad_group.setLayout(broad_layout)
        control_layout.addWidget(broad_group)
        
        control_layout.addStretch()
        self.tabs.addTab(control_tab, "🎛️ Controls")
        
        # TAB 2: LOGS
        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)
        
        self.log_table = QTableWidget()
        self.log_table.setColumnCount(3)
        self.log_table.setHorizontalHeaderLabels(["Time", "Type", "Message"])
        self.log_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.log_table.verticalHeader().setVisible(False)
        self.log_table.setStyleSheet("QTableWidget { background-color: #1a1a1f; color: #e0e0e0; gridline-color: #333; }")
        
        btn_refresh_log = QPushButton("🔄 Refresh Logs")
        btn_refresh_log.clicked.connect(self.refresh_logs)
        
        log_layout.addWidget(self.log_table)
        log_layout.addWidget(btn_refresh_log)
        
        self.tabs.addTab(log_tab, "📜 History Logs")
        
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(1, 2)
        
        main_layout.addWidget(splitter)
        
        self.load_settings()
        self.refresh_logs()

    def load_settings(self):
        """Load checkbox states"""
        tg_manager.load_config()
        cfg = tg_manager.config
        
        self.token_input.setText(cfg.get("bot_token", ""))
        self.chk_auto_hawk.setChecked(cfg.get("auto_post_hawk_dove", False))
        self.chk_auto_all.setChecked(cfg.get("auto_post_all", False))
        self.chk_auto_summary.setChecked(cfg.get("auto_post_summary", True))
        
        templates = cfg.get("templates", {})
        self.template_edit.setText(templates.get("analysis_update", ""))
        
        self.update_channels()

    def update_channels(self):
        self.chan_table.setRowCount(0)
        channels = tg_manager.config.get("channels", [])
        self.chan_table.setRowCount(len(channels))
        
        for i, ch in enumerate(channels):
            self.chan_table.setItem(i, 0, QTableWidgetItem(ch["name"]))
            self.chan_table.setItem(i, 1, QTableWidgetItem(ch["chat_id"]))
            
            btn_del = QPushButton("❌")
            btn_del.setFixedSize(30, 25)
            btn_del.setStyleSheet("color: red; font-weight: bold;")
            # Use closure to capture chat_id
            btn_del.clicked.connect(lambda checked, cid=ch["chat_id"]: self.delete_channel(cid))
            self.chan_table.setCellWidget(i, 2, btn_del)

    def refresh_logs(self):
        history = tg_manager.history
        self.log_table.setRowCount(len(history))
        for i, entry in enumerate(history):
            self.log_table.setItem(i, 0, QTableWidgetItem(entry["time"]))
            self.log_table.setItem(i, 1, QTableWidgetItem(entry["type"]))
            self.log_table.setItem(i, 2, QTableWidgetItem(entry["msg"]))

    def save_token(self):
        tg_manager.config["bot_token"] = self.token_input.text().strip()
        tg_manager.save_config()
        QMessageBox.information(self, "Saved", "Bot Token Saved!")

    def add_channel(self):
        name = self.input_chan_name.text().strip()
        cid = self.input_chan_id.text().strip()
        if name and cid:
            tg_manager.add_channel(name, cid)
            self.input_chan_name.clear()
            self.input_chan_id.clear()
            self.refresh_table()

    def delete_channel(self, chat_id):
        tg_manager.remove_channel(chat_id)
        self.refresh_table()

    def save_rules(self):
        tg_manager.config["auto_post_hawk_dove"] = self.cb_auto_hawk_dove.isChecked()
        tg_manager.config["auto_post_all"] = self.cb_auto_all.isChecked()
        tg_manager.save_config()

    def save_template(self):
        if "templates" not in tg_manager.config:
            tg_manager.config["templates"] = {}
        tg_manager.config["templates"]["analysis_update"] = self.template_edit.toPlainText()
        tg_manager.save_config()
        QMessageBox.information(self, "Saved", "Template Saved!")

    def manual_broadcast(self):
        msg = self.manual_input.text().strip()
        if msg:
            template = tg_manager.config["templates"].get("manual_alert", "{message}")
            final_msg = template.replace("{message}", msg)
            tg_manager.send_to_all(final_msg)
            self.manual_input.clear()
            QMessageBox.information(self, "Broacast", "Message sent to all channels.")

    def scan_chats(self):
        """Fetch chats and show dialog"""
        if not self.token_input.text():
            QMessageBox.warning(self, "Error", "Please enter and save a Bot Token first.")
            return
            
        # Temporary save to ensure manager has latest token
        tg_manager.config["bot_token"] = self.token_input.text().strip()
        
        QApplication.setOverrideCursor(Qt.WaitCursor)
        found_chats = tg_manager.get_recent_chats()
        QApplication.restoreOverrideCursor()
        
        if not found_chats:
            QMessageBox.information(self, "Scan Result", 
                "No recent chats found.\n\n"
                "💡 Tip: Send a message to your bot or add it to a group, then try again.")
            return
            
        dlg = ChatScannerDialog(found_chats, self)
        if dlg.exec() == QDialog.Accepted and dlg.selected_chat:
            name, cid = dlg.selected_chat
            self.input_chan_name.setText(name)
            self.input_chan_id.setText(cid)
    def test_big_picture(self):
        """Send a dummy Big Picture message"""
        dummy_data = {
            "title": "TEST SUMMARY (Simulation)",
            "key_points": [
                "Fed Signals Rate Cuts in Q3 2026",
                "Inflation Data Shows Significant Cooling", 
                "Gold Prices Expected to Rebound above $2500"
            ],
            "market_implication": "Long Gold, Short USD. Prepare for high volatility."
        }
        
        template = tg_manager.config["templates"].get("session_summary", "")
        bullets = "\n".join([f"• {b}" for b in dummy_data["key_points"]])
        msg = template.format(
            title=dummy_data["title"],
            bullets=bullets,
            strategy=dummy_data["market_implication"]
        )
        
        tg_manager.send_to_all(msg)
        tg_manager.log_activity("TEST", "Sent Test Big Picture")
        self.refresh_logs()
        QMessageBox.information(self, "Test Sent", "Test Big Picture message sent!") 
