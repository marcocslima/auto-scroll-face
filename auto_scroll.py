import cv2
import mediapipe as mp
import pyautogui
import time
import numpy as np
import tkinter as tk
from tkinter import ttk
import threading

# Desativar o fail-safe do PyAutoGUI
pyautogui.FAILSAFE = False

class HeadScrollApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Head Scroll Control")
        self.root.geometry("400x400")
        self.root.resizable(False, False)

        # Variáveis de controle
        self.is_running = False
        self.thread = None

        # Configurações
        self.scroll_interval = 0.05
        self.action_cooldown = 1.0
        self.calibration_frames = 30
        self.scroll_speed_factor = 2.0

        # Variáveis ajustáveis (com valores iniciais do código original)
        self.head_turn_threshold = tk.DoubleVar(value=0.85)  # Valor mais alto para melhor detecção
        self.dead_zone = tk.DoubleVar(value=0.015)
        self.scroll_multiplier = tk.DoubleVar(value=150)

        # Variável para debug
        self.debug_info = tk.StringVar(value="")

        # Criar interface
        self.create_widgets()

    def create_widgets(self):
        # Frame principal
        main_frame = ttk.Frame(self.root, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Título
        title_label = ttk.Label(main_frame, text="Head Scroll Control", font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 20))

        # Botões de controle
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        self.start_button = ttk.Button(button_frame, text="Iniciar", command=self.start_tracking)
        self.start_button.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        self.stop_button = ttk.Button(button_frame, text="Parar", command=self.stop_tracking, state=tk.DISABLED)
        self.stop_button.pack(side=tk.RIGHT, padx=5, expand=True, fill=tk.X)

        # Controles de ajuste
        controls_frame = ttk.LabelFrame(main_frame, text="Configurações", padding=10)
        controls_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        # Head Turn Threshold
        head_turn_frame = ttk.Frame(controls_frame)
        head_turn_frame.pack(fill=tk.X, pady=5)

        head_turn_label = ttk.Label(head_turn_frame, text="Virada da Cabeça (Fator):")
        head_turn_label.pack(side=tk.LEFT)

        head_turn_entry = ttk.Entry(head_turn_frame, textvariable=self.head_turn_threshold, width=8)
        head_turn_entry.pack(side=tk.RIGHT)

        # Dead Zone
        dead_zone_frame = ttk.Frame(controls_frame)
        dead_zone_frame.pack(fill=tk.X, pady=5)

        dead_zone_label = ttk.Label(dead_zone_frame, text="Zona Neutra:")
        dead_zone_label.pack(side=tk.LEFT)

        dead_zone_entry = ttk.Entry(dead_zone_frame, textvariable=self.dead_zone, width=8)
        dead_zone_entry.pack(side=tk.RIGHT)

        # Scroll Multiplier
        scroll_mult_frame = ttk.Frame(controls_frame)
        scroll_mult_frame.pack(fill=tk.X, pady=5)

        scroll_mult_label = ttk.Label(scroll_mult_frame, text="Multripicador do Scroll:")
        scroll_mult_label.pack(side=tk.LEFT)

        scroll_mult_entry = ttk.Entry(scroll_mult_frame, textvariable=self.scroll_multiplier, width=8)
        scroll_mult_entry.pack(side=tk.RIGHT)

        # Status
        self.status_var = tk.StringVar(value="Pronto para iniciar")
        status_label = ttk.Label(main_frame, textvariable=self.status_var, font=("Arial", 10))
        status_label.pack(pady=5)

        # Debug info
        debug_label = ttk.Label(main_frame, textvariable=self.debug_info, font=("Arial", 9))
        debug_label.pack(pady=5)

        # Instruções
        instructions = (
            "Instruções:\n"
            "- Mova a cabeça para cima/baixo para scroll\n"
            "- Vire a cabeça de lado para ir ao início do documento\n"
            "- Aperte ESC para parar o rastreamento\n"
        )
        instructions_label = ttk.Label(main_frame, text=instructions, justify=tk.LEFT)
        instructions_label.pack(pady=5)

        # Bind ESC key to stop tracking
        self.root.bind('<Escape>', lambda e: self.stop_tracking())

    def start_tracking(self):
        if self.is_running:
            return

        self.is_running = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.status_var.set("Iniciando...")

        # Iniciar thread para o processamento de vídeo
        self.thread = threading.Thread(target=self.run_head_tracking)
        self.thread.daemon = True
        self.thread.start()

    def stop_tracking(self):
        if not self.is_running:
            return

        self.is_running = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.status_var.set("Parado...")

        # Aguardar a thread terminar
        if self.thread:
            self.thread.join(timeout=1.0)

    def run_head_tracking(self):
        try:
            # Inicializar MediaPipe Face Mesh
            mp_face_mesh = mp.solutions.face_mesh
            face_mesh = mp_face_mesh.FaceMesh(min_detection_confidence=0.5, min_tracking_confidence=0.5)

            # Capturar vídeo da webcam
            cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                self.status_var.set("Error: Webcam não abre")
                self.stop_tracking()
                return

            # Configurações
            last_scroll_time = time.time()
            last_action_time = time.time()
            calibration_frames = self.calibration_frames
            neutral_position = 0
            neutral_head_rotation = 0
            frame_count = 0

            # Pontos de referência
            NOSE_TIP = 4
            LEFT_EYE = 33  # Canto externo do olho esquerdo
            RIGHT_EYE = 263  # Canto externo do olho direito

            # Histórico de rotação para suavização
            rotation_history = []
            history_size = 5

            self.status_var.set("Calibrando... Mantenha a cabeça na posição neutra")

            while self.is_running and cap.isOpened():
                success, image = cap.read()
                if not success:
                    break

                # Converter para RGB e processar
                image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                results = face_mesh.process(image)

                current_time = time.time()

                if results.multi_face_landmarks:
                    face_landmarks = results.multi_face_landmarks[0]

                    # Obter posição vertical do nariz
                    nose_y = face_landmarks.landmark[NOSE_TIP].y

                    # Obter posições dos olhos para calcular rotação horizontal
                    left_eye_x = face_landmarks.landmark[LEFT_EYE].x
                    right_eye_x = face_landmarks.landmark[RIGHT_EYE].x

                    # Calcular a distância entre os olhos
                    eye_distance = right_eye_x - left_eye_x

                    # Fase de calibração
                    if frame_count < calibration_frames:
                        neutral_position += nose_y
                        neutral_head_rotation += eye_distance
                        frame_count += 1

                        # Atualizar status na interface
                        self.status_var.set(f"Calibrando... {frame_count}/{calibration_frames}")

                        if frame_count == calibration_frames:
                            neutral_position /= calibration_frames
                            neutral_head_rotation /= calibration_frames
                            self.status_var.set("Calibração completa. App Ativado.")
                    else:
                        # Calcular deslocamento em relação à posição neutra
                        displacement = nose_y - neutral_position

                        # Calcular rotação da cabeça
                        rotation_ratio = eye_distance / neutral_head_rotation

                        # Adicionar ao histórico para suavização
                        rotation_history.append(rotation_ratio)
                        if len(rotation_history) > history_size:
                            rotation_history.pop(0)

                        # Calcular média suavizada
                        smooth_rotation = sum(rotation_history) / len(rotation_history)

                        # Obter valores atuais dos controles
                        head_turn_threshold = self.head_turn_threshold.get()
                        dead_zone = self.dead_zone.get()
                        scroll_multiplier = self.scroll_multiplier.get()

                        # Atualizar informações de debug
                        self.debug_info.set(f"Rotação: {smooth_rotation:.3f} (Sensibilidade: {head_turn_threshold})")

                        # Detectar virada de cabeça para a direita
                        if smooth_rotation < head_turn_threshold and current_time - last_action_time > self.action_cooldown:
                            # Virou a cabeça para a direita - voltar ao início do documento
                            self.status_var.set("Ação: Ir para o início")
                            pyautogui.press('home')
                            time.sleep(0.5)  # Esperar um pouco para evitar múltiplas ações
                            last_action_time = current_time
                        else:
                            # Determinar velocidade e direção do scroll normal
                            if abs(displacement) > dead_zone:
                                scroll_amount = int(-displacement * scroll_multiplier * self.scroll_speed_factor)

                                if current_time - last_scroll_time > self.scroll_interval:
                                    pyautogui.scroll(scroll_amount)
                                    last_scroll_time = current_time

                                    # Atualizar status ocasionalmente
                                    if int(current_time * 10) % 30 == 0:
                                        direction = "down" if scroll_amount < 0 else "up"
                                        self.status_var.set(f"Scrolling {direction} (disp: {displacement:.3f})")

                # Pequena pausa para reduzir uso de CPU
                time.sleep(0.01)

            # Liberar recursos
            cap.release()

        except Exception as e:
            # Capturar e mostrar qualquer erro
            self.status_var.set(f"Error: {str(e)}")
            self.debug_info.set(f"Exception: {type(e).__name__}")

        finally:
            # Se a thread terminou, atualizar a interface
            if self.is_running:
                self.stop_tracking()

# Iniciar aplicação
if __name__ == "__main__":
    root = tk.Tk()
    app = HeadScrollApp(root)
    root.mainloop()