import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom"; 
import { ClipCard, ClipData } from "../../components/clip-card/ClipCard";
import { Grid } from "../../components/grid/Grid";
import './ProcessingClips.css';
import { DownloadCloud, RefreshCw } from "lucide-react";
import { JobStatus, ClipResult, getToken, downloadClip } from "../../services/api"; // getJobStatus removido pois usamos SSE

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

export default function ProcessingClipsPage() {
  // 1. Extração do ID diretamente da URL
  const { jobId } = useParams<{ jobId: string }>(); 
  const navigate = useNavigate();

  const [job, setJob]     = useState<JobStatus | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    // 2. Validação de segurança: se o usuário entrar na rota sem ID, volta para o início
    if (!jobId) {
      navigate("/");
      return;
    }

    const token = getToken();
    if (!token) {
      setError("Usuário não autenticado.");
      return;
    }

    // 3. Conexão SSE reativa com o backend recuperando os dados baseados na URL
    const streamUrl = `${import.meta.env.VITE_API_PATH}/jobs/${jobId}/stream?token=${token}`;
    const eventSource = new EventSource(streamUrl);

    eventSource.onmessage = (event) => {
      try {
        const data: JobStatus = JSON.parse(event.data);
        console.log("[SSE Job Status]:", data);
        
        // Trata erro customizado vindo pelo SSE
        if ((data as any).error) {
          setError((data as any).error);
          eventSource.close();
          return;
        }

        setJob(data);

        // Se finalizou ou deu erro de processamento, fecha a conexão
        if (data.status === "COMPLETED" || data.status === "ERROR") {
          eventSource.close();
        }
      } catch (err) {
        console.error("Erro ao fazer parse dos dados SSE:", err);
      }
    };

    eventSource.onerror = () => {
      setError("Conexão com o servidor perdida. O processamento pode continuar em background.");
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  }, [jobId, navigate]);

  // Restante do código de renderização do JSX permanece rigorosamente o mesmo...
  const isDone = job?.status === "COMPLETED";
  const isError = job?.status === "ERROR";
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

          {job?.status === "ERROR" && (
            <p style={{ color: "red", marginTop: 8 }}>
              Ocorreu um erro. Tente novamente.
            </p>
          )}

          {error && (
            <p style={{ color: "red", marginTop: 8 }}>{error}</p>
          )}

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