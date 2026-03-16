import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Grid } from "../../components/grid/Grid";
import placeholderImg from "../../assets/placeholder.png";
import "./SelectPlayer.css";

type PlayerData = {
  id: string;
  name: string;
  image: string;
};

export default function SelectPlayerPage() {
  const mockPlayers: PlayerData[] = [
    { id: "1", name: "Jogador 1", image: placeholderImg },
    { id: "2", name: "Jogador 2", image: placeholderImg },
    { id: "3", name: "Jogador 3", image: placeholderImg },
    { id: "4", name: "Jogador 4", image: placeholderImg },
    { id: "5", name: "Jogador 5", image: placeholderImg },
  ];

  const [selectedPlayer, setSelectedPlayer] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const navigate = useNavigate();

  const handleAdvance = () => {
    if (selectedPlayer) {
      setIsModalOpen(true);
    }
  };

  return (
    <div className="page-container bg-gradient">
      <div className="white-container big">

        <div className="processing-header">
          <h2 className="processing-title">
            Buscando o jogador nº {"<Número digitado pelo usuário>"}
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
              <button className="btn-modal-confirm" onClick={() => { setIsModalOpen(false); navigate("/processing-videos"); }}>
                Sim, gerar clipes ✔
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}