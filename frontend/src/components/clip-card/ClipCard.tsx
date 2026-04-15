import { AlertCircle, PlayCircle, Download } from "lucide-react";
import './ClipCard.css';
import { downloadClip } from "../../services/api";

export type ClipStatus = 'generating' | 'completed' | 'error';

export interface ClipData {
    id: string;
    title: string;
    status: ClipStatus;
    progress?: number; 
    thumbnailUrl?: string;
    duration?: string;
    videoUrl?: string;
}

interface ClipCardProps {
    clip: ClipData;
}

export function ClipCard({ clip }: ClipCardProps) {

    async function handleDownload() {
        if (!clip.videoUrl) return;
            try {
                await downloadClip(clip.videoUrl, clip.title);
            } catch (err) {
                console.error("Erro ao baixar clipe:", err);
                alert("Não foi possível baixar o clipe. Tente novamente.");
            }
    }
    
    // EARLY RETURN: Renderiza o Skeleton se estiver processando
    if (clip.status === 'generating') {
        return (
            <div className="clip-card">
                {/* Parte superior (Mídia) com gradiente claro */}
                <div className="clip-card-media skeleton-shimmer-light"></div>
                
                {/* Parte inferior (Info) com gradiente escuro */}
                <div className="clip-card-info skeleton-shimmer-dark">
                    <div className="skeleton-text-line"></div>
                </div>
            </div>
        );
    }

    // Renderização normal para Concluído ou Erro
    return (
        <div className="clip-card">
            
            <div className={`clip-card-media ${clip.status}`}>
                {clip.status === 'error' && (
                    <div className="media-overlay error">
                        <AlertCircle size={32} color="#EF4444" />
                        <span>Falha ao separar clipe</span>
                    </div>
                )}

                {clip.status === 'completed' && clip.thumbnailUrl && (
                    <>
                        <img src={clip.thumbnailUrl} alt={clip.title} className="thumbnail" />
                        <div className="media-overlay hover-play">
                            <PlayCircle size={48} color="white" />
                        </div>
                    </>
                )}
            </div>

            {clip.status === 'completed' && (
                <div className="clip-card-info">
                    <h3 className="clip-title">{clip.title}</h3>
                    <div className="clip-actions">
                        <button
                            className="download-button"
                            onClick={handleDownload}
                            disabled={!clip.videoUrl}
                            title={clip.videoUrl ? "Baixar clipe" : "URL do clipe não disponível"}
                            aria-label={`Baixar ${clip.title}`}
                        >
                            <Download size={18} />
                        </button>
                    </div>
                </div>
            )}
            
        </div>
    );
}