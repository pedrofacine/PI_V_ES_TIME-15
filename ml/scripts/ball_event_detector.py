"""
Detecção de eventos de interação com a bola.

Responsabilidade única: dado o histórico de posições dos jogadores
e da bola ao longo do vídeo, identificar momentos em que o jogador-alvo
teve contato/proximidade com a bola (ex: um toque, um drible).
"""
from ml.scripts.config import (
    BALL_IOU_THRESHOLD,
    BALL_PROXIMITY_PAD,
    BALL_PROXIMITY_THRESHOLD,
    EVENT_MIN_GAP_SECONDS,
)


class BallEventDetector:
    """
    Detecta eventos de contato/proximidade entre jogador-alvo e bola.

    A detecção considera dois critérios:
      1. IoU (intersecção) mínimo entre bbox do jogador e da bola
      2. Proximidade espacial: centro da bola dentro de um bbox expandido
         do jogador, ou a uma distância proporcional ao tamanho do jogador

    Um cooldown evita registrar múltiplos eventos do mesmo toque (spam).
    """

    def __init__(
        self,
        iou_threshold: float = BALL_IOU_THRESHOLD,
        proximity_pad: float = BALL_PROXIMITY_PAD,
        proximity_threshold: float = BALL_PROXIMITY_THRESHOLD,
        min_gap_seconds: float = EVENT_MIN_GAP_SECONDS,
    ) -> None:
        self.iou_threshold = iou_threshold
        self.proximity_pad = proximity_pad
        self.proximity_threshold = proximity_threshold
        self.min_gap_seconds = min_gap_seconds

    def detect(
        self,
        target_frames: list[int],
        video_metadata: dict,
        target_track_ids: set[str],
        fps: float,
    ) -> list[dict]:
        """
        Identifica eventos de toque do jogador-alvo na bola.

        Args:
            target_frames: Lista ordenada de frames em que o alvo aparece.
            video_metadata: Dicionário {frame_idx: {"tracks": [...], "balls": [...]}}.
            target_track_ids: Conjunto de track_ids atribuídos ao jogador-alvo.
            fps: Taxa de quadros do vídeo (usada para o cooldown).

        Returns:
            Lista de eventos, cada um no formato:
            {"type": "toque", "frame": int, "time": float (segundos)}
        """
        events: list[dict] = []
        last_event_frame = -999
        event_gap_frames = int(fps * self.min_gap_seconds)
        recent_hits = set()
        window = int(fps * 0.3)  # 300ms

        for f_idx in target_frames:
            frame_data = video_metadata.get(f_idx)
            if not frame_data:
                continue

            target_box = self._find_target_box(frame_data["tracks"], target_track_ids)
            if target_box is None:
                continue

            # Verifica contato com qualquer bola detectada no frame
            hit = False

            for ball_box in frame_data["balls"]:
                if self._is_ball_near_player(target_box, ball_box):
                    hit = True
                    recent_hits.add(f_idx)
                    break
            
            has_recent_hit = any(
                (f_idx - past_f) <= window for past_f in recent_hits
            )

            # Limpa hits antigos (opcional mas recomendado)
            recent_hits = {
                past_f for past_f in recent_hits if (f_idx - past_f) <= window
            }

            print(f"[BALL] frame={f_idx} | hit={hit} | recent={has_recent_hit}")

            # DECISÃO FINAL
            if has_recent_hit and (f_idx - last_event_frame > event_gap_frames):
                events.append({
                    "type": "toque",
                    "frame": f_idx,
                    "time": f_idx / fps,
                })
                last_event_frame = f_idx
                print(f"[EVENTO] Toque detectado no frame {f_idx} (tempo {f_idx / fps:.2f}s)")

        return events

    def _find_target_box(
        self,
        tracks: list,
        target_track_ids: set[str],
    ) -> list[float] | None:
        """Retorna o bbox do jogador-alvo neste frame, ou None se não estiver presente."""
        for l, t, r, b, tid in tracks:
            if str(tid) in target_track_ids:
                return [l, t, r, b]
        return None

    def _is_ball_near_player(
        self,
        player_box: list[float],
        ball_box: list[float],
    ) -> bool:
        """
        Determina se a bola está em contato/proximidade com o jogador.

        Três critérios em ordem de rapidez:
          1. IoU direto entre os bboxes
          2. Centro da bola dentro do bbox expandido do jogador
          3. Centro da bola próximo do bbox expandido (dentro de threshold)
        """
        # Critério 1: sobreposição direta
        if self._iou(player_box, ball_box) > self.iou_threshold:
            return True

        # Expande o bbox do jogador
        px1, py1, px2, py2 = player_box
        width = px2 - px1
        height = py2 - py1
        expanded = [
            px1 - width * self.proximity_pad,
            py1 - height * self.proximity_pad,
            px2 + width * self.proximity_pad,
            py2 + height * self.proximity_pad,
        ]

        # Calcula centro da bola
        bx1, by1, bx2, by2 = ball_box
        bcx = (bx1 + bx2) / 2.0
        bcy = (by1 + by2) / 2.0

        # Critério 2: centro da bola dentro do bbox expandido
        if expanded[0] <= bcx <= expanded[2] and expanded[1] <= bcy <= expanded[3]:
            return True

        # Critério 3: distância proporcional ao tamanho do jogador
        dx = max(expanded[0] - bcx, 0, bcx - expanded[2])
        dy = max(expanded[1] - bcy, 0, bcy - expanded[3])
        threshold = max(width, height) * self.proximity_threshold
        return (dx * dx + dy * dy) <= threshold * threshold

    @staticmethod
    def _iou(a: list[float], b: list[float]) -> float:
        """Intersection over Union entre dois bboxes no formato [x1, y1, x2, y2]."""
        xa = max(a[0], b[0])
        ya = max(a[1], b[1])
        xb = min(a[2], b[2])
        yb = min(a[3], b[3])

        inter = max(0, xb - xa) * max(0, yb - ya)
        if inter == 0:
            return 0.0

        area_a = (a[2] - a[0]) * (a[3] - a[1])
        area_b = (b[2] - b[0]) * (b[3] - b[1])
        return inter / float(area_a + area_b - inter)