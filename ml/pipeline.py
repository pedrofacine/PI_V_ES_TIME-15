import cv2
from app.ml.football_adapter import FootballAnalyzer
from app.ml.ocr import JerseyOCR

analyzer = FootballAnalyzer()
ocr = JerseyOCR()

def process_video(video_path):
    cap = cv2.VideoCapture(video_path)

    frames = []

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frames.append(frame)

    cap.release()

    # 👇 roda o modelo do repo
    tracks = analyzer.process_frames(frames)

    players_data = {}

    # tracks["players"][frame_num] → lista de jogadores
    for frame_num, player_tracks in enumerate(tracks["players"]):

        frame = frames[frame_num]

        for player in player_tracks:
            track_id = player["track_id"]
            x1, y1, x2, y2 = player["bbox"]

            h = y2 - y1

            crop = frame[y1:int(y1 + h * 0.6), x1:x2]

            number = ocr.read_number(crop)
            final_number = ocr.update_player(track_id, number)

            if track_id not in players_data:
                players_data[track_id] = {
                    "numbers": [],
                    "final_number": None
                }

            if number:
                players_data[track_id]["numbers"].append(number)

            if final_number:
                players_data[track_id]["final_number"] = final_number

    return players_data