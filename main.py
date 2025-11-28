import sys
import os
import subprocess
import threading
import tempfile
import atexit
from pathlib import Path

def extract_files():
    """Распаковывает необходимые файлы из .exe в папку рядом с ним"""
    if getattr(sys, 'frozen', False):
        exe_dir = Path(sys.executable).parent
    else:
        exe_dir = Path(__file__).parent

    temp_dir = exe_dir / "temp_extracted"
    temp_dir.mkdir(exist_ok=True)

    files_to_extract = [
        ("models", "models"),
        ("realesrgan-ncnn-vulkan.exe", "realesrgan-ncnn-vulkan.exe"),
        ("vcomp140.dll", "vcomp140.dll"),
        ("vcomp140d.dll", "vcomp140d.dll"),
        ("PatrickHand-Regular.ttf", "PatrickHand-Regular.ttf")
    ]

    for src_name, dst_name in files_to_extract:
        src_path = Path(getattr(sys, '_MEIPASS', '.')) / src_name
        dst_path = exe_dir / dst_name

        if not dst_path.exists() and src_path.exists():
            if src_path.is_dir():
                import shutil
                shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
            else:
                with open(src_path, 'rb') as fsrc, open(dst_path, 'wb') as fdst:
                    fdst.write(fsrc.read())

    def cleanup():
        if temp_dir.exists():
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

    atexit.register(cleanup)

extract_files()

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QFileDialog, QTextEdit,
    QProgressBar, QWidget, QMessageBox, QSpacerItem, QSizePolicy,
    QFrame, QStyle, QComboBox
)
from PySide6.QtGui import (
    QFont, QFontDatabase, QIcon, QPixmap, QColor,
    QDragEnterEvent, QDropEvent, QDragMoveEvent,
    Qt, QPainter
)
from PySide6.QtCore import (
    Qt, QTimer, QMimeData, QUrl, Signal, Slot
)

DARK_GREEN = "#2E4A3D"
LIGHT_GREEN = "#4CAF50"
GRAY_BG = "#2D2D2D"
GRAY_TEXT = "#CCCCCC"
LOG_BG = "#3A3A3A"
LOG_TEXT = "#FFFFFF"

class DragDropWidget(QWidget):
    file_dropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setStyleSheet(f"""
            background-color: {GRAY_BG};
            border: 2px dashed {LIGHT_GREEN};
            border-radius: 12px;
            padding: 20px;
        """)
        self.setLayout(QVBoxLayout())
        self.label = QLabel("Перетащите сюда изображение\nили нажмите 'Выбрать файл'")
        self.label.setFont(QFont("Patrick Hand", 14))
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet(f"color: {LIGHT_GREEN};")
        self.layout().addWidget(self.label)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tiff')):
                self.file_dropped.emit(file_path)
                self.label.setText(f"✔️ {Path(file_path).name}")
                self.label.setStyleSheet(f"color: {LIGHT_GREEN}; font-weight: bold;")
            else:
                self.label.setText("❌ Не поддерживаемый формат")
                self.label.setStyleSheet("color: #FF5555; font-weight: bold;")
                QTimer.singleShot(2000, lambda: self.label.setText("Перетащите сюда изображение\nили нажмите 'Выбрать файл'"))
                QTimer.singleShot(2000, lambda: self.label.setStyleSheet(f"color: {LIGHT_GREEN};"))

class StyledButton(QPushButton):
    def __init__(self, text, icon=None, parent=None):
        super().__init__(text, parent)
        self.setFont(QFont("Patrick Hand", 11, QFont.Normal))
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {DARK_GREEN};
                color: white;
                padding: 10px 20px;
                border-radius: 8px;
                min-width: 120px;
            }}
            QPushButton:hover {{
                background-color: {LIGHT_GREEN};
            }}
        """)
        if icon:
            self.setIcon(icon)

class FinchScaler(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FinchScaler")
        self.setFixedSize(900, 700)
        self.setStyleSheet(f"background-color: {GRAY_BG};")

        font_path = "PatrickHand-Regular.ttf"
        if os.path.exists(font_path):
            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id != -1:
                families = QFontDatabase.applicationFontFamilies(font_id)
                if families:
                    self.font_family = families[0]
                else:
                    self.font_family = "Arial"
            else:
                self.font_family = "Arial"
        else:
            self.font_family = "Arial"

        self.init_ui()
        self.process = None
        self.output_path = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_process)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        title_label = QLabel("FinchScaler")
        title_label.setFont(QFont(self.font_family, 22, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet(f"color: {LIGHT_GREEN}; margin-bottom: 10px;")
        layout.addWidget(title_label)

        self.drop_widget = DragDropWidget()
        self.drop_widget.file_dropped.connect(self.set_input_file)
        layout.addWidget(self.drop_widget)

        btn_layout = QHBoxLayout()
        select_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon)
        select_btn = StyledButton("Выбрать файл", icon=select_icon)
        select_btn.clicked.connect(self.browse_file)
        btn_layout.addStretch()
        btn_layout.addWidget(select_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        model_layout = QHBoxLayout()
        model_label = QLabel("Модель:")
        model_label.setFont(QFont(self.font_family, 11))
        model_label.setStyleSheet(f"color: {GRAY_TEXT};")
        self.model_combo = QComboBox()
        self.model_combo.setFont(QFont(self.font_family, 11))
        self.model_combo.setStyleSheet(f"""
            background-color: {LOG_BG};
            color: {LOG_TEXT};
            border: 1px solid #444;
            border-radius: 6px;
            padding: 5px;
        """)
        self.model_combo.setMinimumWidth(500)
        self.model_combo.setMaximumWidth(1000)
        self.model_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        model_dir = Path("models")
        models_param = set()
        models_pth = set()

        if model_dir.exists():
            for file in model_dir.glob("*.param"):
                model_name = file.stem
                models_param.add(model_name)
            for file in model_dir.glob("*.pth"):
                model_name = file.stem
                models_pth.add(model_name)
        else:
            models_param.update([
                "realesr-animevideov3-x2",
                "realesr-animevideov3-x3",
                "realesr-animevideov3-x4",
                "realesrgan-x4plus",
                "realesrgan-x4plus-anime"
            ])

        if models_param:
            for model in sorted(models_param):
                self.model_combo.addItem(model, model)
        elif models_pth:
            for model in sorted(models_pth):
                self.model_combo.addItem(model, model)
            QMessageBox.warning(
                self,
                "Внимание",
                "Обнаружены .pth модели. Они не поддерживаются realesrgan-ncnn-vulkan.exe. Требуются .param/.bin файлы."
            )
        else:
            self.model_combo.addItem("realesr-animevideov3-x2", "realesr-animevideov3-x2")
            self.model_combo.addItem("realesrgan-x4plus", "realesrgan-x4plus")

        # Устанавливаем realesrgan-x4plus-anime как активный, если есть
        if "realesrgan-x4plus-anime" in models_param:
            index = self.model_combo.findText("realesrgan-x4plus-anime")
            if index != -1:
                self.model_combo.setCurrentIndex(index)

        model_layout.addWidget(model_label)
        model_layout.addWidget(self.model_combo)

        # Выбор масштаба
        scale_layout = QHBoxLayout()
        scale_label = QLabel("Масштаб:")
        scale_label.setFont(QFont(self.font_family, 11))
        scale_label.setStyleSheet(f"color: {GRAY_TEXT};")
        self.scale_combo = QComboBox()
        self.scale_combo.setFont(QFont(self.font_family, 11))
        self.scale_combo.setStyleSheet(f"""
            background-color: {LOG_BG};
            color: {LOG_TEXT};
            border: 1px solid #444;
            border-radius: 6px;
            padding: 5px;
        """)
        self.scale_combo.setMinimumWidth(100)
        self.scale_combo.setMaximumWidth(200)
        self.scale_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.scale_combo.addItem("x2", "2")
        self.scale_combo.addItem("x4", "4")

        scale_layout.addWidget(scale_label)
        scale_layout.addWidget(self.scale_combo)

        # Объединяем модели и масштаб в одну строку
        combined_layout = QHBoxLayout()
        combined_layout.addLayout(model_layout)
        combined_layout.addLayout(scale_layout)
        layout.addLayout(combined_layout)

        run_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        self.start_btn = StyledButton("Запустить апскейлинг", icon=run_icon)
        self.start_btn.clicked.connect(self.start_upscale)
        layout.addWidget(self.start_btn)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setVisible(False)
        self.progress.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {LIGHT_GREEN};
                border-radius: 5px;
                background-color: {LOG_BG};
                height: 10px;
            }}
            QProgressBar::chunk {{
                background-color: {LIGHT_GREEN};
                border-radius: 5px;
            }}
        """)
        layout.addWidget(self.progress)

        log_label = QLabel("Логи:")
        log_label.setFont(QFont(self.font_family, 11))
        log_label.setStyleSheet(f"color: {GRAY_TEXT};")
        layout.addWidget(log_label)

        self.log_text = QTextEdit()
        self.log_text.setFont(QFont(self.font_family, 10))
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet(f"""
            background-color: {LOG_BG};
            color: {LOG_TEXT};
            border: 1px solid #444;
            border-radius: 8px;
            padding: 10px;
            selection-background-color: {LIGHT_GREEN};
            selection-color: black;
        """)
        layout.addWidget(self.log_text)

        layout.addItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding))

    def set_input_file(self, file_path):
        self.input_file = file_path
        self.log_text.append(f"📁 Выбран файл: {Path(file_path).name}")

    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите изображение", "", "Изображения (*.png *.jpg *.jpeg *.bmp *.tiff)"
        )
        if file_path:
            self.set_input_file(file_path)

    def start_upscale(self):
        if not hasattr(self, 'input_file') or not os.path.exists(self.input_file):
            QMessageBox.critical(self, "Ошибка", "Сначала выберите изображение!")
            return

        model_data = self.model_combo.currentData()
        if not model_data:
            QMessageBox.critical(self, "Ошибка", "Укажите модель!")
            return

        scale_data = self.scale_combo.currentData()
        if not scale_data:
            QMessageBox.critical(self, "Ошибка", "Укажите масштаб!")
            return

        exe_path = "realesrgan-ncnn-vulkan.exe"
        if not os.path.exists(exe_path):
            QMessageBox.critical(self, "Ошибка", "Не найден realesrgan-ncnn-vulkan.exe!")
            return

        # Проверяем, есть ли .pth модель (если да — ошибка)
        model_dir = Path("models")
        pth_model_path = model_dir / f"{model_data}.pth"
        if pth_model_path.exists():
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Модель {model_data}.pth не поддерживается этим бинарником. Требуется .param/.bin файл."
            )
            return

        input_p = Path(self.input_file)
        output_dir = input_p.parent / "FinchScaled"
        output_dir.mkdir(exist_ok=True)

        output_path = output_dir / f"{input_p.stem}_upscaled{input_p.suffix}"

        cmd = [
            exe_path,
            "-i", str(input_p),
            "-o", str(output_path),
            "-n", str(model_data),
            "-s", str(scale_data),  # масштаб x2 или x4
            "-t", "512",  # размер тайла 512 — фиксит мозаику
            "-v"  # verbose для прогресса
        ]

        self.log_text.clear()
        self.log_text.append(f"⚙️ Запуск: {' '.join(cmd)}\n")
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.start_btn.setEnabled(False)

        def run_process():
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                cwd=os.getcwd()
            )

        threading.Thread(target=run_process, daemon=True).start()
        self.timer.start(300)

    def check_process(self):
        if self.process and self.process.poll() is not None:
            self.timer.stop()
            self.progress.setVisible(False)
            self.start_btn.setEnabled(True)

            stdout, _ = self.process.communicate()
            if stdout:
                self.log_text.append(stdout)

            lines = stdout.strip().splitlines()
            for line in lines:
                if "Progress:" in line and "%" in line:
                    try:
                        percent_str = line.split("Progress:")[1].strip().split("%")[0]
                        percent = int(percent_str)
                        if 0 <= percent <= 100:
                            self.progress.setValue(percent)
                    except:
                        pass

            input_p = Path(self.input_file)
            output_dir = input_p.parent / "FinchScaled"
            output_path = output_dir / f"{input_p.stem}_upscaled{input_p.suffix}"

            if self.process.returncode == 0:
                self.log_text.append(f"\n✅ Готово! Сохранено как: {output_path.name}")
                QMessageBox.information(self, "Успех", "Апскейлинг завершён успешно!")
                if output_path.exists():
                    os.startfile(str(output_dir))
            else:
                self.log_text.append(f"\n❌ Ошибка (код {self.process.returncode})")
                QMessageBox.critical(self, "Ошибка", "Произошла ошибка при апскейлинге.")

    def closeEvent(self, event):
        if self.process and self.process.poll() is None:
            reply = QMessageBox.question(
                self, 'Подтверждение',
                "Процесс всё ещё работает. Завершить его перед закрытием?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.process.terminate()
                self.timer.stop()
            else:
                event.ignore()
                return
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FinchScaler()
    window.show()
    sys.exit(app.exec())