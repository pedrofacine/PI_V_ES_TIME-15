interface PlayerCardProps {
    id: string;
    imageUrl: string;
    isSelected: boolean;
    onSelect: (id: string) => void;
}

export function PlayerCard({ id, imageUrl, isSelected, onSelect }: PlayerCardProps) {
    return (
        <div 
            className={`player-card ${isSelected ? 'selected' : ''}`}
            onClick={() => onSelect(id)}
        >
            <div className="player-image-wrapper">
                <img src={imageUrl} alt={`Jogador ${id}`} />
            </div>
            <p className="player-id-text">{id}</p>
        </div>
    );
}