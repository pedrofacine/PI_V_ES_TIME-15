class BallTracker:
    def __init__(self, max_missing=10):
        self.last_box = None
        self.last_frame = None
        self.velocity = (0, 0)
        self.missing_frames = 0
        self.max_missing = max_missing

    def update(self, frame_idx, detections):
        """
        detections: lista de bboxes da bola no frame atual
        """

        # Se detectou bola: usa ela
        if detections:
            box = detections[0]  # assume 1 bola
            cx = (box[0] + box[2]) / 2
            cy = (box[1] + box[3]) / 2

            if self.last_box:
                prev_cx = (self.last_box[0] + self.last_box[2]) / 2
                prev_cy = (self.last_box[1] + self.last_box[3]) / 2

                self.velocity = (cx - prev_cx, cy - prev_cy)

            self.last_box = box
            self.last_frame = frame_idx
            self.missing_frames = 0

            return box

        # Não detectou: prever posição
        if self.last_box and self.missing_frames < self.max_missing:
            vx, vy = self.velocity

            predicted = [
                self.last_box[0] + vx,
                self.last_box[1] + vy,
                self.last_box[2] + vx,
                self.last_box[3] + vy,
            ]

            self.last_box = predicted
            self.missing_frames += 1

            return predicted

        # perdeu completamente
        self.last_box = None
        return None