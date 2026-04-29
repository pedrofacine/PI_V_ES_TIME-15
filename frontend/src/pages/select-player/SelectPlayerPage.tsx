import { useEffect, useState } from "react";
import { Grid } from "../../components/grid/Grid";
import placeholderImg from "../../assets/placeholder.png";
import "./SelectPlayer.css";
import { getToken, JobStatus } from "../../services/api";

type SelectPlayerProps = {
  job: JobStatus;
  jobId: string;
};


export default function SelectPlayerView({job, jobId}: SelectPlayerProps) {
  const [selectedPlayer, setSelectedPlayer] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isRefining, setIsRefining] = useState(false);
  const [hasAutoOpened, setHasAutoOpened] = useState(false);

  useEffect(() => {
    if (!hasAutoOpened && job.candidates && job.candidates.length > 0) {
      
      const targetCandidate = job.candidates.find(c => c.is_target);
      
      if (targetCandidate) {
        setSelectedPlayer(targetCandidate.id);
        setIsModalOpen(true);
        setHasAutoOpened(true);
      }
    }
  }, [job.candidates, hasAutoOpened]);

  const handleAdvance = () => {
    if (selectedPlayer) {
      setIsModalOpen(true);
    }
  };

  const handleConfirmPlayer = async () => {
      try {
          const startTs = Number(localStorage.getItem("job_start_ts") ?? 0);
          const endTs = Number(localStorage.getItem("job_end_ts") ?? 0);

          await fetch(`${import.meta.env.VITE_API_PATH}/jobs/${jobId}/confirm`, {
              method: "POST",
              headers: {
                  "Content-Type": "application/json",
                  "Authorization": `Bearer ${getToken()}`
              },
              body: JSON.stringify({
                  candidate_signature: selectedPlayer,
                  start_ts: startTs,
                  end_ts: endTs,
              })
          });
          setIsModalOpen(false);
      } catch (err) {
          console.error("Erro ao confirmar o jogador:", err);
          alert("Falha ao iniciar o recorte. Tente novamente.");
      }
  };

  const handleRefineSearch = async () => {
    setIsRefining(true);
    // TODO: Chamar api.post(`/jobs/${jobId}/refine`) para acionar o DEEP_SCAN no Python
  };

  // Pega os dados completos do jogador selecionado para exibir no Modal
  const selectedCandidateData = job.candidates?.find(c => c.id === selectedPlayer);
  const candidatesList = job.candidates || [];

  return (
    <div className="page-container bg-gradient">
      <div className="white-container big">

        <div className="processing-header">
          <h2 className="processing-title">
            {job.status === "FAST_SCAN" || isRefining
              ? "Analisando jogadores em campo..." 
              : `Buscando o jogador nº ${job.candidates?.[0]?.number || "..."}`}
          </h2>

          <div className="progress-bar-container">
            <div className={`progress-bar-fill ${job.status === "WAITING_USER" ? "finished" : "animating"}`} />
          </div>
        </div>

        <p className="select-text">
          {candidatesList.length > 0 
            ? "Selecione o jogador que você deseja:" 
            : "Procurando candidatos..."}
        </p>

        <Grid>
          {candidatesList.map(candidate => {
            // Monta a URL da imagem. Se a sua API roda numa porta diferente, pode ser necessário 
            // concatenar a base URL aqui, ex: `${import.meta.env.VITE_API_BASE_URL}${candidate.image}`
            const imageUrl = `${import.meta.env.VITE_API_PATH}${candidate.image}` || placeholderImg;

            return (
              <div
                key={candidate.id}
                className={`player-card ${selectedPlayer === candidate.id ? "selected" : ""}`}
                onClick={() => setSelectedPlayer(candidate.id)}
              >
                <img src={imageUrl} alt={candidate.name} />
                <p>
                  {candidate.name}
                  {selectedPlayer === candidate.id && " - Selecionado"}
                </p>
                <div style={{
                    width: '16px', height: '16px', borderRadius: '50%', 
                    backgroundColor: candidate.color_hex, margin: '0 auto',
                    border: '1px solid #ccc'
                }} title={`Cor detectada: ${candidate.color_hex}`} />
              </div>
            );
          })}
        </Grid>

        <div className="clips-actions-container">
          <button 
            className="btn btn-secondary" 
            onClick={handleRefineSearch}
            disabled={job.status !== "WAITING_USER"}
          >
            Meu jogador não está aqui
          </button>

          <button
            className="btn btn-primary"
            disabled={!selectedPlayer}
            onClick={handleAdvance}
          >
            Avançar →
          </button>
        </div>
      </div>

      {isModalOpen && selectedCandidateData && (
        <div className="modal-overlay">
          <div className="modal-card">
            <h2 className="modal-title">Esse é o seu jogador?</h2>
            
            <div className="modal-player-preview">
              <div className="preview-image-container">
                 <img 
                    src={selectedCandidateData.image ? `${import.meta.env.VITE_API_PATH}${selectedCandidateData.image}` : placeholderImg} 
                    alt="Preview" 
                  />
                 <div className="player-id-label">{selectedCandidateData.name}</div>
              </div>
            </div>

            <div className="modal-footer-buttons">
              <button className="btn-modal-cancel" onClick={() => setIsModalOpen(false)}>
                Não, a IA errou ✖
              </button>
              <button className="btn-modal-confirm" onClick={handleConfirmPlayer}>
                Sim, gerar clipes ✔
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}