import { AlertCircle, Download, Trash2 } from "lucide-react";
import './ClipCard.css';
import { downloadClip, deleteClip } from "../../services/api";

export type ClipStatus = 'generating' | 'completed' | 'error' | 'expired';

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
    onDeleted?: (clipId: string) => void;
}

export function ClipCard({ clip, onDeleted }: ClipCardProps) {

    async function handleDownload() {
        if (!clip.videoUrl) return;
            try {
                await downloadClip(clip.videoUrl, clip.title);
            } catch (err) {
                console.error("Erro ao baixar clipe:", err);
                alert("Não foi possível baixar o clipe. Tente novamente.");
            }
    }

    async function handleDelete() {
        if (!window.confirm(`Apagar o clipe "${clip.title}"? Essa ação não pode ser desfeita.`)) return;
        try {
            await deleteClip(clip.id);
            onDeleted?.(clip.id);
        } catch (err) {
            console.error("Erro ao apagar clipe:", err);
            alert("Não foi possível apagar o clipe. Tente novamente.");
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

    // Renderização normal para Concluído, Erro ou Expirado
    return (
        <div className="clip-card">
            
            <div className={`clip-card-media ${clip.status}`}>
                {clip.status === 'error' && (
                    <div className="media-overlay error">
                        <AlertCircle size={32} color="#EF4444" />
                        <span>Falha ao separar clipe</span>
                    </div>
                )}

                {clip.status === 'expired' && (
                    <div className="media-overlay expired">
                        <AlertCircle size={32} color="#9ca3af" />
                        <span style={{ marginTop: '8px' }}>Clipe expirado</span>
                    </div>
                )}

                {clip.status === 'completed' && clip.videoUrl && (
                    <video
                        className="clip-video"
                        src={`${import.meta.env.VITE_API_PATH}${clip.videoUrl}`}
                        controls
                        preload="auto"
                    />
                )}
            </div>

            {(clip.status === 'completed' || clip.status === 'expired') && (
                <div className="clip-card-info">
                    <h3 className="clip-title">{clip.title}</h3>
                    <div className="clip-actions">
                        {clip.status === 'completed' && (
                            <button
                                className="download-button"
                                onClick={handleDownload}
                                disabled={!clip.videoUrl}
                                title={clip.videoUrl ? "Baixar clipe" : "URL do clipe não disponível"}
                                aria-label={`Baixar ${clip.title}`}
                            >
                                <Download size={18} />
                            </button>
                        )}
                        <button
                            className="delete-button"
                            onClick={handleDelete}
                            title="Apagar clipe"
                            aria-label={`Apagar ${clip.title}`}
                        >
                            <Trash2 size={18} />
                        </button>
                    </div>
                </div>
            )}
            
        </div>
    );
}