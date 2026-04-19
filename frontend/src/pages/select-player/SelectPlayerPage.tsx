import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Grid } from "../../components/grid/Grid";
import placeholderImg from "../../assets/placeholder.png";
import "./SelectPlayer.css";
import { JobStatus } from "../../services/api";

type SelectPlayerProps = {
  job: JobStatus;
  jobId: string;
};


export default function SelectPlayerView({job, jobId}: SelectPlayerProps) {
  const mockPlayers = [
    { id: "1", name: "Jogador 1", image: placeholderImg },
    { id: "2", name: "Jogador 2", image: placeholderImg },
  ];

  const [selectedPlayer, setSelectedPlayer] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isRefining, setIsRefining] = useState(false);


  const handleAdvance = () => {
    if (selectedPlayer) {
      setIsModalOpen(true);
    }
  };

  const handleConfirmPlayer = async () => {
    // Quando o backend estiver pronto, chamaremos a API aqui:
    // await api.post(`/jobs/${jobId}/confirm`, { playerId: selectedPlayer });
    
    setIsModalOpen(false);
    // Nota: NÃO damos navigate() aqui! 
    // Quando a API responder, o status do Job muda para TRACKING via SSE
    // e o Container pai troca a tela sozinho!
  };

  const handleRefineSearch = async () => {
    setIsRefining(true);
    // TODO: Chamar api.post(`/jobs/${jobId}/refine`) para acionar o DEEP_SCAN no Python
  };

  return (
    <div className="page-container bg-gradient">
      <div className="white-container big">

        <div className="processing-header">
          <h2 className="processing-title">
            {job.status === "FAST_SCAN" || isRefining
              ? "Analisando jogadores em campo..." 
              : "Buscando o jogador nº <Número>"}
          </h2>

          <div className="progress-bar-container">
            <div className="progress-bar-fill animating" />
          </div>
        </div>

        <p className="select-text">Selecione o jogador que você deseja:</p>

        <Grid>
          {mockPlayers.map(player => (
            <div
              key={player.id}
              className={`player-card ${selectedPlayer === player.id ? "selected" : ""}`}
              onClick={() => setSelectedPlayer(player.id)}
            >
              <img src={player.image} alt={player.name} />
              <p>
                {player.name}
                {selectedPlayer === player.id && " - Selecionado"}
              </p>
            </div>
          ))}
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

      {isModalOpen && (
        <div className="modal-overlay">
          <div className="modal-card">
            <h2 className="modal-title">Esse é o seu jogador?</h2>
            
            <div className="modal-player-preview">
              <div className="preview-image-container">
                 <img src={placeholderImg} alt="Preview" />
                 <div className="player-id-label">{"<id do jogador>"}</div>
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