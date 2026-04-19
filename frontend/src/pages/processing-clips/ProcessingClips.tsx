import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom"; 
import { ClipCard, ClipData } from "../../components/clip-card/ClipCard";
import { Grid } from "../../components/grid/Grid";
import './ProcessingClips.css';
import { DownloadCloud, RefreshCw } from "lucide-react";
import { JobStatus, ClipResult, getToken, downloadClip } from "../../services/api"; // getJobStatus removido pois usamos SSE

type ProcessingClipsProps = {
  job: JobStatus;
};

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
    videoUrl:     clip.file_url,
  };
}

const skeletonClip: ClipData = {
  id:           "skeleton-processing",
  title:        "Gerando clipe...",
  status:       "generating",
  thumbnailUrl: undefined,
  duration:     "--:--",
};

export default function ProcessingClipsView({ job }: ProcessingClipsProps) {
  const navigate = useNavigate();
  const isDone = job.status === "COMPLETED";
  const isError = job.status === "ERROR";
  const clips  = job.clips ?? [];

  function getTitle() {
    switch (job.status) {
      case "TRACKING":  return "Recortando os lances do jogador escolhido...";
      case "COMPLETED": return "Os clipes estão prontos!";
      case "ERROR":     return "Erro no processamento.";
      default:          return "Processando...";
    }
  }

function handleDownloadAll() {
    clips.forEach((clip, index) => {
        const title = `CLIP#${String(index + 1).padStart(3, "0")}`;
        downloadClip(clip.file_url, title).catch(err =>
            console.error(`Erro ao baixar ${title}:`, err)
        );
    });
}

  return (
    <div className="page-container bg-gradient">
      <div className="white-container big">

        <div className="processing-header">
          <h2 className="processing-title">{getTitle()}</h2>

          <div className="progress-bar-container">
            <div className={`progress-bar-fill ${isDone ? "finished" : isError ? "error" : "animating"}`} />
          </div>
        </div>

        <Grid>
          {clips.map((clip, i) => (
            <ClipCard
              key={clip.id}
              clip={toClipData(clip, i)}
            />
          ))}
          {job?.status === "TRACKING" &&
            <ClipCard
              key={skeletonClip.id}
              clip={skeletonClip}
            />

          }
        </Grid>

        {!isDone && clips.length === 0 && (
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