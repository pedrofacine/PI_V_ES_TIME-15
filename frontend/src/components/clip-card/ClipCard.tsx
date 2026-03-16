import { AlertCircle, PlayCircle, Download } from "lucide-react";
import './ClipCard.css';

export type ClipStatus = 'generating' | 'completed' | 'error';

export interface ClipData {
    id: string;
    title: string;
    status: ClipStatus;
    progress?: number; 
    thumbnailUrl?: string;
    duration?: string;
}

interface ClipCardProps {
    clip: ClipData;
}

export function ClipCard({ clip }: ClipCardProps) {
    
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
                        <Download size={18} className="download-button"/>
                    </div>
                </div>
            )}
            
        </div>
    );
}