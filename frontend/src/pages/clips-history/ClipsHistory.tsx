import React, { useMemo, useState } from "react";
import { ClipCard, ClipData } from "../../components/clip-card/ClipCard";
import { Grid } from "../../components/grid/Grid";
import './ClipsHistory.css'
import placeholderImg from '../../assets/placeholder.png';
import { Search, ChevronDown } from "lucide-react";

type ClipWithDate = ClipData & { generatedAt: string; videoUrl?: string };

export default function ClipsHistory() {
    const [search, setSearch] = useState("");
    const [sortBy, setSortBy] = useState<"recent" | "oldest">("recent");
    const [modalSession, setModalSession] = useState<{ date: string, clips: ClipWithDate[] } | null>(null);

    const mockClips: ClipWithDate[] = [
        { id: '1', title: 'CLIP#001', status: 'completed', thumbnailUrl: placeholderImg, duration: '0:15', generatedAt: '27/08/2025 - 10:41' },
        { id: '2', title: 'CLIP#002', status: 'completed', thumbnailUrl: placeholderImg, duration: '0:15', generatedAt: '27/08/2025 - 10:41' },
        { id: '3', title: 'CLIP#003', status: 'completed', thumbnailUrl: placeholderImg, duration: '0:15', generatedAt: '27/08/2025 - 10:41' },
        { id: '4', title: 'CLIP#004', status: 'completed', thumbnailUrl: placeholderImg, duration: '0:15', generatedAt: '27/08/2025 - 10:41' },
        { id: '5', title: 'CLIP#005', status: 'completed', thumbnailUrl: placeholderImg, duration: '0:15', generatedAt: '27/08/2025 - 10:41' },
        { id: '6', title: 'CLIP#006', status: 'completed', thumbnailUrl: placeholderImg, duration: '0:15', generatedAt: '27/08/2025 - 10:41' },
        { id: '7', title: 'CLIP#007', status: 'completed', thumbnailUrl: placeholderImg, duration: '0:15', generatedAt: '26/08/2025 - 18:25' },
        { id: '8', title: 'CLIP#008', status: 'completed', thumbnailUrl: placeholderImg, duration: '0:15', generatedAt: '26/08/2025 - 18:25' },
        { id: '9', title: 'CLIP#009', status: 'completed', thumbnailUrl: placeholderImg, duration: '0:15', generatedAt: '26/08/2025 - 18:25' },
        { id: '10', title: 'CLIP#010', status: 'completed', thumbnailUrl: placeholderImg, duration: '0:15', generatedAt: '26/08/2025 - 18:25' },
        { id: '11', title: 'CLIP#011', status: 'completed', thumbnailUrl: placeholderImg, duration: '0:15', generatedAt: '25/08/2025 - 14:07' },
        { id: '12', title: 'CLIP#012', status: 'completed', thumbnailUrl: placeholderImg, duration: '0:15', generatedAt: '25/08/2025 - 14:07' },
    ];

    const filteredClips = useMemo(() => {
        const normalized = search.trim().toLowerCase();
        const filtered = mockClips.filter(clip =>
            !normalized || clip.title.toLowerCase().includes(normalized)
        );

        return filtered.sort((a, b) => {
            if (sortBy === "recent") return b.generatedAt.localeCompare(a.generatedAt);
            return a.generatedAt.localeCompare(b.generatedAt);
        });
    }, [search, sortBy]);

    const clipsByDate = useMemo(() => {
        return filteredClips.reduce<Record<string, ClipWithDate[]>>((acc, clip) => {
            acc[clip.generatedAt] = acc[clip.generatedAt] || [];
            acc[clip.generatedAt].push(clip);
            return acc;
        }, {});
    }, [filteredClips]);

    return (
        <div className="page-container bg-gradient">
            <div className="white-container big">
                <header className="history-header">
                    <h1 className="history-title">Histórico de Clipes</h1>
                    <div className="history-actions">
                        <div className="input-wrapper">
                            <Search className="input-icon" size={16} />
                            <input
                                type="text"
                                className="input-base with-icon"
                                value={search}
                                onChange={(e) => setSearch(e.target.value)}
                                placeholder="Buscar clipe ou jogador..."
                                aria-label="Buscar clipe ou jogador"
                            />
                        </div>

                        <label className="filter-input">
                            <span>Filtrar por:</span>
                            <select value={sortBy} onChange={(e) => setSortBy(e.target.value as any)}>
                                <option value="recent">Mais recente</option>
                                <option value="oldest">Mais antigo</option>
                            </select>
                            <ChevronDown size={16} />
                        </label>
                    </div>
                </header>

                <div className="progress-bar-container">
                    <div className="progress-bar-fill finished" />
                </div>

                <div className="scrollable-content">
                    {Object.entries(clipsByDate).map(([date, clips], index) => (
                        <React.Fragment key={date}>
                            <section className="clip-group">
                                <div className="clip-group-header">
                                    <span>Clipes gerados em: </span>
                                    <span className="clip-group-date">{date}</span>
                                </div>

                                <Grid>
                                    {clips.slice(0, 5).map(clip => (
                                        <ClipCard key={clip.id} clip={clip} />
                                    ))}
                                    <div
                                        className="see-all-card"
                                        onClick={() => setModalSession({ date, clips })}
                                    >
                                        <span>Ver Todos</span>
                                        <span className="see-all-count">{clips.length} clipes</span>
                                    </div>
                                </Grid>
                            </section>
                            {index < Object.entries(clipsByDate).length - 1 && <hr className="group-separator" />}
                        </React.Fragment>
                    ))}
                </div>

                <div className="footer-note">
                    Os clipes ficam armazenados por até 14 dias após sua geração no nosso site
                </div>
            </div>

            {modalSession && (
                <div className="modal-overlay" onClick={() => setModalSession(null)}>
                    <div className="modal-content" onClick={e => e.stopPropagation()}>
                        <div className="modal-header">
                            <span>Clipes gerados em: <strong>{modalSession.date}</strong></span>
                            <button onClick={() => setModalSession(null)}>✕</button>
                        </div>
                        <Grid>
                            {modalSession.clips.map(clip => (
                                <ClipCard key={clip.id} clip={clip} />
                            ))}
                        </Grid>
                    </div>
                </div>
            )}
        </div>
    );
}