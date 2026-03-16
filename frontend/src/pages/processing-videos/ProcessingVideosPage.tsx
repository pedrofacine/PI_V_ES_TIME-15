import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { ClipCard } from "../../components/clip-card/ClipCard";
import { Grid } from "../../components/grid/Grid";
import "../processing-clips/ProcessingClips.css";
import "./ProcessingVideos.css";

const LOADING_DURATION_MS = 4000;
const SKELETON_COUNT = 12;

const loadingClips = Array.from({ length: SKELETON_COUNT }, (_, i) => ({
  id: String(i + 1),
  title: `CLIP#00${i + 1}`,
  status: "generating" as const,
  progress: 0,
}));

export default function ProcessingVideosPage() {
  const navigate = useNavigate();

  useEffect(() => {
    const timer = setTimeout(() => {
      navigate("/processing-clips");
    }, LOADING_DURATION_MS);
    return () => clearTimeout(timer);
  }, [navigate]);

  return (
    <div className="page-container bg-gradient">
      <div className="white-container big">
        <div className="processing-header">
          <h2 className="processing-title">
            Processando e recortando os vídeos...
          </h2>

          <div className="progress-bar-container">
            <div className="progress-bar-fill animating" />
          </div>
        </div>

        <Grid>
          {loadingClips.map((clip) => (
            <ClipCard key={clip.id} clip={clip} />
          ))}
        </Grid>
      </div>
    </div>
  );
}
