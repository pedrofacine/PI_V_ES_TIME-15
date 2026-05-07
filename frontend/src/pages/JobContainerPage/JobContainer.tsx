import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getToken, JobStatus } from "../../services/api";
import SelectPlayerView from "../select-player/SelectPlayerPage";
import ProcessingClipsView from "../processing-clips/ProcessingClips";
import "./JobContainer.css";

export default function JobContainerPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();

  const [job, setJob] = useState<JobStatus | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!jobId) {
      navigate("/");
      return;
    }

    const token = getToken();
    if (!token) {
      setError("Usuário não autenticado.");
      return;
    }

    const streamUrl = `${import.meta.env.VITE_API_PATH}/jobs/${jobId}/stream?token=${token}`;
    const eventSource = new EventSource(streamUrl);

    eventSource.onmessage = (event) => {
      try {
        const data: JobStatus = JSON.parse(event.data);
        console.log("[SSE Job Status]:", data);

        if ((data as any).error) {
          setError((data as any).error);
          eventSource.close();
          return;
        }

        setJob(data);

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

  if (error) {
    return (
      <div className="job-container-page">
        <div className="job-state-card">
          <h2 className="job-state-title error">Erro</h2>
          <p className="job-state-message">{error}</p>
          <button className="btn btn-secondary" onClick={() => navigate("/")}>
            Voltar ao Início
          </button>
        </div>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="job-container-page">
        <div className="job-state-card">
          <h2 className="job-state-title">Conectando ao servidor...</h2>
          <div className="progress-bar-container">
            <div className="progress-bar-fill animating" />
          </div>
        </div>
      </div>
    );
  }

  if (job.status === "FAST_SCAN" || job.status === "WAITING_USER" || job.status === "DEEP_SCAN") {
    return <SelectPlayerView job={job} jobId={jobId!} />;
  }

  if (job.status === "TRACKING" || job.status === "EXTRACTING" || job.status === "COMPLETED" || job.status === "ERROR") {
    return <ProcessingClipsView job={job} />;
  }

  return (
    <div className="job-container-page">
      <div className="job-state-card">
        <h2 className="job-state-title">Iniciando análise do vídeo...</h2>
        <div className="progress-bar-container">
          <div className="progress-bar-fill animating" />
        </div>
      </div>
    </div>
  );
}
