"""
Detecção de anomalias cinemáticas no histórico de rastreamento.

Responsabilidade única: dado o video_metadata produzido pelo pipeline,
calcular velocidade e aceleração de cada track (jogadores e bola) e
identificar frames com comportamento cinemático anômalo.
"""
import math
from collections import defaultdict

from scripts.config import (
    KINEMATIC_COOLDOWN_SECONDS,
    KINEMATIC_MIN_ACCEL,
    KINEMATIC_MIN_VELOCITY,
    KINEMATIC_STD_MULTIPLIER,
)


class KinematicAnalyzer:
    """
    Analisa anomalias cinemáticas (picos de velocidade e aceleração)
    em todos os objetos rastreados: jogadores e bola.

    Estratégia dupla:
      1. Threshold fixo: filtra ruído de baixa intensidade
      2. Desvio-padrão: adapta-se à escala do vídeo/câmera
    """

    def __init__(
        self,
        min_velocity: float = KINEMATIC_MIN_VELOCITY,
        min_accel: float = KINEMATIC_MIN_ACCEL,
        std_multiplier: float = KINEMATIC_STD_MULTIPLIER,
        cooldown_seconds: float = KINEMATIC_COOLDOWN_SECONDS,
    ) -> None:
        self.min_velocity = min_velocity
        self.min_accel = min_accel
        self.std_multiplier = std_multiplier
        self.cooldown_seconds = cooldown_seconds

    def analyze(self, video_metadata: dict, fps: float) -> list[dict]:
        """
        Identifica anomalias cinemáticas em jogadores e bola.

        Args:
            video_metadata: {frame_idx: {"tracks": [[l,t,r,b,tid],...],
                                         "balls":  [[x1,y1,x2,y2],...]}}
            fps: Taxa de quadros do vídeo.

        Returns:
            Lista de eventos, cada um no formato:
            {"type": "pico_velocidade"|"pico_aceleracao",
             "object": "bola"|"jogador",
             "track_id": str,
             "frame": int,
             "time": float,
             "value": float}
        """
        positions = self._collect_positions(video_metadata)
        events: list[dict] = []

        for track_id, pos_list in positions.items():
            if len(pos_list) < 3:
                continue

            is_ball = track_id.startswith("ball")
            object_label = "bola" if is_ball else "jogador"

            velocities, accelerations = self._compute_kinematics(pos_list)
            events.extend(
                self._detect_anomalies(
                    pos_list, velocities, "pico_velocidade", object_label, track_id, fps
                )
            )
            events.extend(
                self._detect_anomalies(
                    pos_list, accelerations, "pico_aceleracao", object_label, track_id, fps
                )
            )

        events.sort(key=lambda e: e["frame"])
        return events

    # ------------------------------------------------------------------
    # COLETA DE POSIÇÕES
    # ------------------------------------------------------------------

    def _collect_positions(
        self, video_metadata: dict
    ) -> dict[str, list[tuple[int, float, float]]]:
        """
        Agrupa posições (frame, cx, cy) por track_id.

        Bolas recebem IDs sintéticos "ball_0", "ball_1", etc.,
        atribuídos por ordem de aparição em cada frame.
        """
        tracks: dict[str, list[tuple[int, float, float]]] = defaultdict(list)

        for frame_idx in sorted(video_metadata.keys()):
            frame_data = video_metadata[frame_idx]

            for l, t, r, b, tid in frame_data.get("tracks", []):
                cx = (l + r) / 2.0
                cy = (t + b) / 2.0
                tracks[str(tid)].append((frame_idx, cx, cy))

            for ball_idx, (x1, y1, x2, y2) in enumerate(frame_data.get("balls", [])):
                cx = (x1 + x2) / 2.0
                cy = (y1 + y2) / 2.0
                tracks[f"ball_{ball_idx}"].append((frame_idx, cx, cy))

        return tracks

    # ------------------------------------------------------------------
    # CÁLCULO CINEMÁTICO
    # ------------------------------------------------------------------

    def _compute_kinematics(
        self, positions: list[tuple[int, float, float]]
    ) -> tuple[list[float], list[float]]:
        """
        Calcula velocidade e aceleração para uma sequência de posições.

        Usa Δframes real entre amostras consecutivas para lidar com
        FRAME_SKIP sem inflar os valores.
        """
        velocities: list[float] = [0.0]
        for i in range(1, len(positions)):
            f_prev, cx_prev, cy_prev = positions[i - 1]
            f_curr, cx_curr, cy_curr = positions[i]
            delta = max(1, f_curr - f_prev)
            dist = math.sqrt((cx_curr - cx_prev) ** 2 + (cy_curr - cy_prev) ** 2)
            velocities.append(dist / delta)

        accelerations: list[float] = [0.0, 0.0]
        for i in range(1, len(velocities)):
            f_prev = positions[i - 1][0]
            f_curr = positions[i][0]
            delta = max(1, f_curr - f_prev)
            accelerations.append(abs(velocities[i] - velocities[i - 1]) / delta)

        # Alinha tamanhos
        while len(accelerations) < len(positions):
            accelerations.append(0.0)

        return velocities, accelerations

    # ------------------------------------------------------------------
    # DETECÇÃO DE ANOMALIAS
    # ------------------------------------------------------------------

    def _detect_anomalies(
        self,
        positions: list[tuple[int, float, float]],
        values: list[float],
        event_type: str,
        object_label: str,
        track_id: str,
        fps: float,
    ) -> list[dict]:
        """
        Flageía índices onde o valor excede threshold fixo E desvio-padrão.

        Aplica cooldown entre eventos do mesmo track para evitar spam.
        """
        if not values:
            return []

        mean_v = sum(values) / len(values)
        variance = sum((v - mean_v) ** 2 for v in values) / len(values)
        std_v = math.sqrt(variance)

        # Se std = 0 o objeto está parado; a condição estatística nunca é satisfeita
        stat_threshold = mean_v + self.std_multiplier * std_v

        fixed_threshold = (
            self.min_velocity if event_type == "pico_velocidade" else self.min_accel
        )

        cooldown_frames = int(fps * self.cooldown_seconds)
        last_event_frame = -cooldown_frames - 1

        events: list[dict] = []
        for i, (frame_idx, _, _) in enumerate(positions):
            v = values[i]
            if v <= fixed_threshold or v <= stat_threshold:
                continue
            if frame_idx - last_event_frame <= cooldown_frames:
                continue

            events.append(
                {
                    "type": event_type,
                    "object": object_label,
                    "track_id": track_id,
                    "frame": frame_idx,
                    "time": frame_idx / fps,
                    "value": round(v, 2),
                }
            )
            last_event_frame = frame_idx

        return events
