import sys
import subprocess
import socket
import time
import pkg_resources
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QTextEdit, QPushButton,
    QLabel, QLineEdit, QHBoxLayout, QFrame, QProgressBar,
    QScrollArea
)
from PySide6.QtGui import (
    QTextCursor, QIcon, QPixmap, QPainter, QColor
)
from PySide6.QtCore import QTimer, Qt, QSize, QThread, Signal, QObject

class Theme:
    """Uygulama için renk paletlerini ve stil şablonunu yönetir."""
    dark = {
        "bg_color": "#1e1e2f",
        "frame_color": "#2a2a3f",
        "text_color": "#e0e0e0",
        "secondary_text_color": "#a0a0b0",
        "accent_color": "#8a79f7",
        "accent_hover_color": "#a29bfe",
        "user_bubble_color": "#8a79f7",
        "bot_bubble_color": "#2a2a3f",
        "border_color": "#4a4a6a",
        "danger_color": "#ff7675",
    }
    light = {
        "bg_color": "#f4f6f8",
        "frame_color": "#ffffff",
        "text_color": "#1f2937",
        "secondary_text_color": "#6b7280",
        "accent_color": "#6c5ce7",
        "accent_hover_color": "#8a79f7",
        "user_bubble_color": "#6c5ce7",
        "bot_bubble_color": "#e5e7eb",
        "border_color": "#d1d5db",
        "danger_color": "#e53e3e",
    }

    @staticmethod
    def get_stylesheet(theme):
        """Seçilen tema için QSS stil şablonu oluşturur."""
        return f"""
            QWidget#mainWidget {{
                background-color: {theme['bg_color']};
            }}
            QScrollArea, QWidget#scrollContent {{
                background: transparent;
                border: none;
            }}

            QFrame#header {{
                background: {theme['frame_color']};
                border-radius: 15px;
                border: 1px solid {theme['border_color']};
            }}
            QLabel#title {{
                color: {theme['text_color']};
                font-size: 22px;
                font-weight: bold;
                background: transparent;
            }}
            QLabel#linkLabel {{
                color: {theme['accent_color']};
                font-size: 14px;
                background: transparent;
            }}
            QLabel#linkLabel a {{
                color: {theme['accent_color']};
                text-decoration: none;
            }}
            QLabel#linkLabel a:hover {{
                text-decoration: underline;
            }}
            QPushButton#themeToggleButton {{
                background-color: transparent;
                border: none;
                border-radius: 18px;
            }}
            QPushButton#exitButton {{
                background-color: transparent;
                color: {theme['danger_color']};
                border: 1px solid {theme['danger_color']};
                border-radius: 8px;
                font-weight: bold;
                padding: 8px 16px;
            }}
            QPushButton#exitButton:hover {{
                background-color: {theme['danger_color']};
                color: white;
            }}

            QFrame#userBubble {{
                background-color: {theme['user_bubble_color']};
                border-radius: 18px; border-bottom-right-radius: 5px;
            }}
            QFrame#userBubble QLabel {{
                color: white; font-size: 15px; background:transparent;
            }}
            QFrame#userBubble QLabel#timeLabel {{
                color: rgba(255, 255, 255, 0.8); font-size: 11px;
            }}
            QFrame#botBubble {{
                background-color: {theme['bot_bubble_color']};
                border: 1px solid {theme['border_color']};
                border-radius: 18px; border-bottom-left-radius: 5px;
            }}
            QFrame#botBubble QLabel {{
                color: {theme['text_color']}; font-size: 15px; background:transparent;
            }}
            QFrame#botBubble QLabel#timeLabel {{
                color: {theme['secondary_text_color']}; font-size: 11px;
            }}
            QLabel#avatarLabel {{
                font-weight: bold;
                color: {theme['text_color']};
                background-color: {theme['bot_bubble_color']};
                border: 1px solid {theme['border_color']};
                border-radius: 20px;
                qproperty-alignment: 'AlignCenter';
            }}

            QFrame#inputFrame {{
                background: {theme['frame_color']};
                border-radius: 15px;
                border: 1px solid {theme['border_color']};
            }}
            QLineEdit#messageInput {{
                background-color: transparent;
                border: none;
                font-size: 15px;
                color: {theme['text_color']};
            }}
            QPushButton#sendButton {{
                background-color: {theme['accent_color']};
                border: none;
                border-radius: 18px;
            }}
            QPushButton#sendButton:hover {{
                background-color: {theme['accent_hover_color']};
            }}
        """

class WorkerSignals(QObject):
    finished = Signal()
    error = Signal(tuple)
    result = Signal(object)
    progress = Signal(int)
    log = Signal(str)

class InstallWorker(QThread):
    def __init__(self, packages_to_install):
        super().__init__()
        self.packages = packages_to_install
        self.signals = WorkerSignals()

    def run(self):
        try:
            total_packages = len(self.packages)
            for i, package in enumerate(self.packages):
                self.signals.log.emit(f"� {package} paketi yükleniyor...")
                subprocess.check_output([sys.executable, "-m", "pip", "install", package], stderr=subprocess.STDOUT)
                self.signals.log.emit(f"✅ {package} başarıyla yüklendi")
                progress = int(((i + 1) / total_packages) * 100)
                self.signals.progress.emit(progress)
            self.signals.result.emit("Tüm paketler yüklendi.")
        except subprocess.CalledProcessError as e:
            error_output = e.output.decode('utf-8', errors='ignore') if e.output else "Çıktı yok."
            self.signals.log.emit(f"❌ Bir paket yüklenemedi.\nHata: {error_output}")
            self.signals.error.emit((type(e), e, "Yükleme başarısız oldu"))
        except Exception as e:
            self.signals.error.emit((type(e), e, "Beklenmedik bir hata oluştu"))
        finally:
            self.signals.finished.emit()

class ApiServiceWorker(QThread):
    def __init__(self, url, payload):
        super().__init__()
        self.url = url
        self.payload = payload
        self.signals = WorkerSignals()

    def run(self):
        try:
            import requests
            response = requests.post(self.url, json=self.payload, timeout=90)
            response.raise_for_status()
            self.signals.result.emit(response.json())
        except requests.exceptions.RequestException as e:
            self.signals.error.emit((type(e), e, f"Ağ Hatası: {e}"))
        except Exception as e:
            self.signals.error.emit((type(e), e, "Beklenmedik bir hata oluştu"))
        finally:
            self.signals.finished.emit()

class ServiceManager:
    def __init__(self):
        self.processes = []

    def is_port_in_use(self, port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(("127.0.0.1", port)) == 0

    def start_service(self, service_name, app_path, port):
        """
        Servisi başlatır ve çıktısını bir log dosyasına yönlendirir.
        Dönüş değeri: (mesaj, log_dosya_adı)
        """
        log_file_name = f"{service_name.lower().replace(' ', '_')}_service.log"
        if self.is_port_in_use(port):
            return f"[ATLANDI] {service_name} zaten {port} portunda çalışıyor.", log_file_name
        try:
            log_file = open(log_file_name, "w", encoding='utf-8')
            process = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", app_path, "--port", str(port)],
                stdout=log_file, stderr=subprocess.STDOUT
            )
            self.processes.append({'process': process, 'log_file': log_file})
            return f"[OK] {service_name} başlatıldı (port {port}).", log_file_name
        except Exception as e:
            return f"[BAŞARISIZ] {service_name} başlatılamadı: {e}", log_file_name

    def wait_for_port(self, port, timeout=30):
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.is_port_in_use(port): return True
            time.sleep(0.5)
        return False

    def stop_all_services(self):
        print("Tüm arka plan servisleri sonlandırılıyor...")
        for p_info in self.processes:
            process = p_info['process']
            log_file = p_info['log_file']
            try:
                process.terminate()
                process.wait(timeout=5)
                print(f"Süreç {process.pid} sonlandırıldı.")
            except Exception as e:
                print(f"Süreç {process.pid} sonlandırılamadı: {e}")
            finally:
                if not log_file.closed:
                    log_file.close()
        self.processes = []
        print("Tüm servisler durduruldu.")

class ModernLoadingScreen(QWidget):
    def __init__(self, service_manager):
        super().__init__()
        self.service_manager = service_manager
        self.main_window = None
        self.install_worker = None
        self.setWindowTitle("NLP Sistem Başlatılıyor")
        self.setFixedSize(800, 600)
        self.setup_ui()
        self.dependencies = self.check_requirements()
        self.current_step = 0
        self.boot_timer = QTimer(self)
        self.boot_timer.timeout.connect(self.run_boot_sequence)
        self.boot_timer.start(500)

    def setup_ui(self):
        self.setStyleSheet("""
            QWidget { background-color: #1e1e2f; color: #e0e0e0; font-family: 'Segoe UI', Arial, sans-serif; }
            QTextEdit { background-color: #2a2a3f; border: 1px solid #4a4a6a; border-radius: 8px; padding: 10px; color: #00ff88; font-family: 'Consolas', 'Courier New', monospace; font-size: 14px; }
            QPushButton { background-color: #5a67d8; border: none; border-radius: 8px; color: white; font-size: 16px; font-weight: bold; padding: 12px 24px; margin-top: 10px; }
            QPushButton:hover { background-color: #667eea; }
            QPushButton:pressed { background-color: #434190; }
            QPushButton:disabled { background-color: #4a4a6a; }
            QProgressBar { border: 1px solid #4a4a6a; border-radius: 8px; text-align: center; color: #e0e0e0; background-color: #2a2a3f; }
            QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #5a67d8, stop:1 #00ff88); border-radius: 6px; }
        """)
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 40, 40, 40)
        header = QLabel("🚀 NLP Sistem Başlatma Sırası")
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet("font-size: 28px; font-weight: bold; color: #667eea; margin-bottom: 20px;")
        layout.addWidget(header)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        layout.addWidget(self.log_box)
        self.status_label = QLabel("Sistem başlatılıyor...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size: 16px; color: #00ff88; margin-top: 10px;")
        layout.addWidget(self.status_label)
        self.install_button = QPushButton("📦 Eksik Paketleri Yükle")
        self.install_button.clicked.connect(self.start_installation)
        self.install_button.hide()
        layout.addWidget(self.install_button)

    def check_requirements(self):
        """
        requirements.txt dosyasını kontrol eder.
        Not: Bu fonksiyon, lxml[html_clean] gibi eski "extra" tanımlarından kaynaklanan
        UnknownExtra hatalarını önlemek için değiştirilmiştir. Sadece ana paket adının
        varlığını kontrol eder.
        """
        installed, missing = [], []
        try:
            with open("requirements.txt", "r", encoding='utf-8') as f:
                packages = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            for req_string in packages:
                try:
                    req = pkg_resources.Requirement.parse(req_string)
                    pkg_resources.get_distribution(req.project_name)
                    installed.append(req_string)
                except pkg_resources.DistributionNotFound:
                    missing.append(req_string)
        except FileNotFoundError:
            self.append_log("[UYARI] requirements.txt bulunamadı.")
        except Exception as e:
            self.append_log(f"[HATA] Gereksinimler kontrol edilirken bir sorun oluştu: {e}")
        return {"installed": installed, "missing": missing}

    def append_log(self, text):
        self.log_box.append(text)
        self.log_box.moveCursor(QTextCursor.End)
        QApplication.processEvents()

    def update_progress(self, value, status=""):
        self.progress_bar.setValue(value)
        if status: self.status_label.setText(status)

    def run_boot_sequence(self):
        steps = [
            (10, "🔍 Sistem başlatma sırası başlatıldı..."), (20, "📋 requirements.txt kontrol ediliyor..."),
            (30, "Bağımlılıklar analiz ediliyor..."), (40, "Eksik paketler kontrol ediliyor..."),
        ]
        if self.current_step < len(steps):
            progress, message = steps[self.current_step]
            self.update_progress(progress, message)
            self.append_log(message)
            self.current_step += 1
        else:
            self.boot_timer.stop()
            self.evaluate_dependencies()

    def evaluate_dependencies(self):
        self.append_log("✅ Yüklü paketler:")
        for pkg in self.dependencies["installed"]: self.append_log(f"   ✓ {pkg}")
        if self.dependencies["missing"]:
            self.append_log("❌ Eksik paketler tespit edildi:")
            for pkg in self.dependencies["missing"]: self.append_log(f"   ✗ {pkg}")
            self.update_progress(50, "Kullanıcı eylemi bekleniyor...")
            self.install_button.show()
        else:
            self.append_log("🎉 Tüm gereksinimler karşılandı!")
            self.update_progress(60, "Tüm gereksinimler tamam.")
            self.start_all_services()

    def start_installation(self):
        self.install_button.setEnabled(False)
        self.install_button.setText("Yükleniyor...")
        self.update_progress(55, "Yükleme başlatılıyor...")
        self.install_worker = InstallWorker(self.dependencies["missing"])
        self.install_worker.signals.log.connect(self.append_log)
        self.install_worker.signals.progress.connect(lambda p: self.update_progress(55 + int(p * 0.2), f"Yükleniyor... {p}%"))
        self.install_worker.signals.finished.connect(self.on_installation_finished)
        self.install_worker.signals.error.connect(lambda e: self.append_log(f"HATA: {e[-1]}"))
        self.install_worker.start()

    def on_installation_finished(self):
        self.append_log("🎉 Yükleme işlemi tamamlandı!")
        self.install_button.hide()
        self.dependencies = self.check_requirements()
        if self.dependencies["missing"]:
                 self.append_log("⚠️ Bazı paketler hala eksik görünüyor.")
                 self.update_progress(75, "Yükleme başarısız oldu.")
        else:
            self.update_progress(75, "Yükleme başarılı.")
            self.start_all_services()

    def start_all_services(self):
        self.update_progress(80, "🚀 Arka plan servisleri başlatılıyor...")
        self.append_log("🚀 Arka plan servisleri başlatılıyor...")
        services = [
            ("Re-Ranker", "re-rank:app", 8002), ("Retrieve Service", "retrieve:app", 8000),
            ("Strategic Router", "router:app", 8001), ("Main Gateway", "gate:app", 8003)
        ]
        all_started = True
        for i, (name, path, port) in enumerate(services):
            self.append_log(f"🔄 {name} başlatılıyor...")
            result, log_file = self.service_manager.start_service(name, path, port)
            self.append_log(f"   {result}")
            QApplication.processEvents()

            if "BAŞARISIZ" in result:
                all_started = False
                self.append_log(f"❌ {name} başlatılamadı. Detaylar için bkz: {log_file}")
                continue

            if self.service_manager.wait_for_port(port):
                self.append_log(f"✅ {name}, {port} portunda hazır.")
            else:
                all_started = False
                if "ATLANDI" not in result:
                    self.append_log(f"❌ {name} zamanında hazır hale gelmedi. Detaylar için bkz: {log_file}")
            
            self.update_progress(80 + int((i + 1) / len(services) * 20))

        if all_started:
            self.append_log("🎉 Tüm servisler hazır!")
            self.update_progress(100, "Sistem hazır!")
            QTimer.singleShot(1500, self.open_main_app)
        else:
            self.append_log("❌ Bir veya daha fazla servis başlatılamadı. Lütfen yukarıdaki logları ve oluşturulan *.log dosyalarını kontrol edin.")
            self.update_progress(100, "Servis başlatma başarısız oldu.")

    def open_main_app(self):
        self.close()
        self.main_window = ChatbotGUI()
        self.main_window.showFullScreen()

class ChatMessageWidget(QFrame):
    """Tek bir sohbet mesajını (balon) temsil eden widget."""
    def __init__(self, message, is_user=True):
        super().__init__()
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M")

        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(0, 5, 0, 5)

        avatar_label = QLabel()
        avatar_label.setObjectName("avatarLabel")
        avatar_label.setFixedSize(40, 40)

        bubble_frame = QFrame()
        bubble_layout = QVBoxLayout(bubble_frame)
        bubble_layout.setContentsMargins(15, 10, 15, 10)
        bubble_layout.setSpacing(5)

        self.message_label = QLabel(message)
        self.message_label.setWordWrap(True)
        self.message_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        time_label = QLabel(timestamp)
        time_label.setObjectName("timeLabel")

        bubble_layout.addWidget(self.message_label)
        bubble_layout.addWidget(time_label, 0, Qt.AlignRight)

        if is_user:
            avatar_label.setText("S")
            bubble_frame.setObjectName("userBubble")
            main_layout.addStretch()
            main_layout.addWidget(bubble_frame)
            main_layout.addWidget(avatar_label)
        else:
            avatar_label.setText("B")
            bubble_frame.setObjectName("botBubble")
            main_layout.addWidget(avatar_label)
            main_layout.addWidget(bubble_frame)
            main_layout.addStretch()

    def set_text(self, text):
        self.message_label.setText(text)

class ChatbotGUI(QWidget):
    """Tema desteği sunan modern sohbet arayüzü."""
    def __init__(self):
        super().__init__()
        self.api_worker = None
        self.typing_indicator = None
        self.current_theme = 'dark'
        self.setup_ui()
        self.apply_theme()
        self.add_welcome_message()
        self.api_url = "http://127.0.0.1:8003/ask_intelligent"

    def setup_ui(self):
        self.setWindowTitle("TercihChat")
        self.setObjectName("mainWidget")
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(20, 20, 20, 20)

        header_frame = QFrame()
        header_frame.setObjectName("header")
        header_frame.setFixedHeight(70)
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(25, 0, 25, 0)
        header_layout.setSpacing(15)

        logo_label = QLabel()
        logo_pixmap = QPixmap("tercihnoktam.jpg")
        if not logo_pixmap.isNull():
            logo_label.setPixmap(logo_pixmap.scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            print("Uyarı: 'tercihnoktam.jpg' dosyası bulunamadı veya yüklenemedi.")

        title = QLabel("TercihChat")
        title.setObjectName("title")

        link_label = QLabel('<a href="http://tercihnoktam.com">tercihnoktam.com</a>')
        link_label.setObjectName("linkLabel")
        link_label.setOpenExternalLinks(True)
        link_label.setCursor(Qt.PointingHandCursor)

        self.theme_toggle_button = QPushButton()
        self.theme_toggle_button.setObjectName("themeToggleButton")
        self.theme_toggle_button.setFixedSize(40, 40)
        self.theme_toggle_button.setCursor(Qt.PointingHandCursor)
        self.theme_toggle_button.clicked.connect(self.toggle_theme)

        exit_button = QPushButton("Çıkış")
        exit_button.setObjectName("exitButton")
        exit_button.setCursor(Qt.PointingHandCursor)
        exit_button.clicked.connect(self.close)

        header_layout.addWidget(logo_label)
        header_layout.addWidget(title)
        header_layout.addWidget(link_label)
        header_layout.addStretch()
        header_layout.addWidget(self.theme_toggle_button)
        header_layout.addWidget(exit_button)
        main_layout.addWidget(header_frame)
        main_layout.addSpacing(15)

        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_widget = QWidget()
        self.chat_widget.setObjectName("scrollContent")
        self.chat_layout_inner = QVBoxLayout(self.chat_widget)
        self.chat_layout_inner.setContentsMargins(10, 10, 10, 10)
        self.chat_layout_inner.setSpacing(15)
        self.chat_layout_inner.addStretch()
        self.chat_scroll.setWidget(self.chat_widget)
        main_layout.addWidget(self.chat_scroll)
        main_layout.addSpacing(15)

        input_frame = QFrame()
        input_frame.setObjectName("inputFrame")
        input_frame.setFixedHeight(70)
        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(10, 10, 10, 10)
        input_layout.setSpacing(15)

        self.message_input = QLineEdit()
        self.message_input.setObjectName("messageInput")
        self.message_input.setPlaceholderText("Mesajınızı buraya yazın...")
        self.message_input.returnPressed.connect(self.send_message)
        input_layout.addWidget(self.message_input)

        self.send_button = QPushButton()
        self.send_button.setObjectName("sendButton")
        self.send_button.setFixedSize(50, 50)
        self.send_button.setCursor(Qt.PointingHandCursor)
        self.send_button.clicked.connect(self.send_message)
        input_layout.addWidget(self.send_button)
        main_layout.addWidget(input_frame)

    def apply_theme(self):
        """Mevcut temayı uygular ve ikonları günceller."""
        theme_data = Theme.dark if self.current_theme == 'dark' else Theme.light
        self.setStyleSheet(Theme.get_stylesheet(theme_data))

        icon_color = "white" if self.current_theme == 'dark' else "black"

        theme_icon_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{icon_color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>""" if self.current_theme == 'dark' else f"""<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{icon_color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>"""
        theme_pixmap = QPixmap()
        theme_pixmap.loadFromData(theme_icon_svg.encode('utf-8'))
        self.theme_toggle_button.setIcon(QIcon(theme_pixmap))
        self.theme_toggle_button.setIconSize(QSize(24, 24))

        send_icon_svg = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>"""
        send_pixmap = QPixmap()
        send_pixmap.loadFromData(send_icon_svg.encode('utf-8'))
        self.send_button.setIcon(QIcon(send_pixmap))
        self.send_button.setIconSize(QSize(24, 24))

    def toggle_theme(self):
        """Koyu ve açık tema arasında geçiş yapar."""
        self.current_theme = 'light' if self.current_theme == 'dark' else 'dark'
        self.apply_theme()

    def add_welcome_message(self):
        welcome_text = "Merhaba! 👋 Ben TercihChat. Size nasıl yardımcı olabilirim?"
        self.add_message(welcome_text, is_user=False)

    def add_message(self, message, is_user=True):
        message_widget = ChatMessageWidget(message, is_user)
        self.chat_layout_inner.insertWidget(self.chat_layout_inner.count() - 1, message_widget)
        QTimer.singleShot(50, self.scroll_to_bottom)
        return message_widget

    def scroll_to_bottom(self):
        self.chat_scroll.verticalScrollBar().setValue(self.chat_scroll.verticalScrollBar().maximum())

    def send_message(self):
        message = self.message_input.text().strip()
        if not message: return
        self.add_message(message, is_user=True)
        self.message_input.clear()
        self.toggle_input_enabled(False)
        self.typing_indicator = self.add_message("...", is_user=False)
        
        self.typing_timer = QTimer(self)
        self.typing_dots = 1
        def animate_typing():
            self.typing_dots = (self.typing_dots % 3) + 1
            self.typing_indicator.set_text("." * self.typing_dots)
        self.typing_timer.timeout.connect(animate_typing)
        self.typing_timer.start(400)

        self.api_worker = ApiServiceWorker(self.api_url, {"query": message})
        self.api_worker.signals.result.connect(self.on_api_success)
        self.api_worker.signals.error.connect(self.on_api_error)
        self.api_worker.signals.finished.connect(self.on_api_finished)
        self.api_worker.start()

    def on_api_success(self, data):
        answer = data.get('answer', "Üzgünüm, yanıtı işleyemedim.")
        self.typing_indicator.set_text(answer)

    def on_api_error(self, error_tuple):
        _, _, error_message = error_tuple
        self.typing_indicator.set_text(f"Üzgünüm, bir hata oluştu: {error_message}")

    def on_api_finished(self):
        if hasattr(self, 'typing_timer') and self.typing_timer.isActive():
            self.typing_timer.stop()
        self.typing_indicator = None
        self.toggle_input_enabled(True)

    def toggle_input_enabled(self, enabled):
        self.message_input.setEnabled(enabled)
        self.send_button.setEnabled(enabled)
        if enabled: self.message_input.setFocus()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    service_manager = ServiceManager()
    app.aboutToQuit.connect(service_manager.stop_all_services)
    
    loader = ModernLoadingScreen(service_manager)
    loader.show()
    
    sys.exit(app.exec())
