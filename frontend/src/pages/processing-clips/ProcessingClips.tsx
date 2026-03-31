import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { ClipCard, ClipData } from "../../components/clip-card/ClipCard";
import { Grid } from "../../components/grid/Grid";
import './ProcessingClips.css';
import { DownloadCloud, RefreshCw } from "lucide-react";
import { getJobStatus, JobStatus, ClipResult } from "../../services/api";

const API_HOST        = "http://localhost:8000";
const POLL_INTERVAL   = 3000;

// Converte ClipResult (backend) → ClipData (ClipCard)
function toClipData(clip: ClipResult, index: number): ClipData {
  return {
    id:           clip.id,
    title:        `CLIP#${String(index + 1).padStart(3, "0")}`,
    status:       "completed",
    thumbnailUrl: undefined,
    duration:     `${Math.floor(clip.duration / 60)}:${String(
                    Math.round(clip.duration % 60)
                  ).padStart(2, "0")}`,
  };
}

export default function ProcessingClipsPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const jobId    = (location.state as any)?.jobId as string | undefined;

  const [job, setJob]     = useState<JobStatus | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!jobId) {
      navigate("/");
      return;
    }

    const poll = async () => {
      try {
        const data = await getJobStatus(jobId);
        setJob(data);
        if (data.status === "COMPLETED" || data.status === "ERROR") {
          clearInterval(interval);
        }
      } catch (err: any) {
        setError(err.message);
        clearInterval(interval);
      }
    };

    poll(); // chamada imediata ao entrar na página
    const interval = setInterval(poll, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [jobId]);

  const isDone = job?.status === "COMPLETED";
  const clips  = job?.clips ?? [];

  function getTitle() {
    switch (job?.status) {
      case "PENDING":   return "Aguardando na fila...";
      case "SCANNING":  return "Procurando o jogador no vídeo...";
      case "TRACKING":  return "Recortando os lances do jogador escolhido...";
      case "COMPLETED": return "Os clipes estão prontos!";
      case "ERROR":     return "Erro no processamento.";
      default:          return "Iniciando processamento...";
    }
  }

  function handleDownloadAll() {
    clips.forEach((clip) => {
      const a  = document.createElement("a");
      a.href     = `${API_HOST}${clip.file_url}`;
      a.download = `clip_${clip.id}.mp4`;
      a.click();
    });
  }

  return (
    <div className="page-container bg-gradient">
      <div className="white-container big">

        <div className="processing-header">
          <h2 className="processing-title">{getTitle()}</h2>

          {job?.status === "ERROR" && (
            <p style={{ color: "red", marginTop: 8 }}>
              Ocorreu um erro. Tente novamente.
            </p>
          )}

          {error && (
            <p style={{ color: "red", marginTop: 8 }}>{error}</p>
          )}

          <div className="progress-bar-container">
            <div className={`progress-bar-fill ${isDone ? "finished" : "animating"}`} />
          </div>
        </div>

        <Grid>
          {clips.map((clip, i) => (
            <ClipCard
              key={clip.id}
              clip={toClipData(clip, i)}
            />
          ))}
        </Grid>

        {!isDone && clips.length === 0 && !error && (
          <p style={{ textAlign: "center", color: "#888", margin: "32px 0" }}>
            Os clipes aparecerão aqui conforme forem gerados...
          </p>
        )}

        <div className="clips-actions-container">
          <button
            className="btn icon btn-secondary"
            onClick={() => navigate("/")}
          >
            <RefreshCw size={18} />
            Fazer nova análise
          </button>

          <button
            className="btn icon btn-primary"
            disabled={!isDone || clips.length === 0}
            onClick={handleDownloadAll}
          >
            <DownloadCloud size={18} />
            Baixar todos os clipes
          </button>
        </div>

      </div>
    </div>
  );
}