import React, { useEffect, useMemo, useState } from "react";
import { ClipCard, ClipData } from "../../components/clip-card/ClipCard";
import { Grid } from "../../components/grid/Grid";
import './ClipsHistory.css'
import { Search, ChevronDown } from "lucide-react";
import { listClips, ClipHistoryGroup } from "../../services/api";

type ClipWithDate = ClipData & { generatedAt: string; videoUrl?: string };

function groupToClips(group: ClipHistoryGroup): ClipWithDate[] {
    return group.clips.map((clip, i) => ({
        id:           clip.id,
        title:        `CLIP#${String(i + 1).padStart(3, "0")}`,
        status:       "completed" as const,
        thumbnailUrl: undefined,
        duration:     clip.duration,
        generatedAt:  group.generated_at,
        videoUrl:     clip.file_url,
    }));
}

export default function ClipsHistory() {
    const [groups, setGroups]   = useState<ClipHistoryGroup[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError]     = useState("");
    const [search, setSearch]   = useState("");
    const [sortBy, setSortBy]   = useState<"recent" | "oldest">("recent");
    const [modalSession, setModalSession] = useState<{ date: string, clips: ClipWithDate[] } | null>(null);

    useEffect(() => {
        listClips()
            .then(setGroups)
            .catch((err) => setError(err.message))
            .finally(() => setLoading(false));
    }, []);

    const allClips: ClipWithDate[] = useMemo(() => {
        return groups.flatMap(groupToClips);
    }, [groups]);

    const filteredClips = useMemo(() => {
        const normalized = search.trim().toLowerCase();
        const filtered = allClips.filter(clip =>
            !normalized || clip.title.toLowerCase().includes(normalized)
        );

        return filtered.sort((a, b) => {
            if (sortBy === "recent") return b.generatedAt.localeCompare(a.generatedAt);
            return a.generatedAt.localeCompare(b.generatedAt);
        });
    }, [allClips, search, sortBy]);

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
                    {loading && (
                        <p style={{ textAlign: "center", color: "#888", margin: "32px 0" }}>
                            Carregando clipes...
                        </p>
                    )}

                    {error && (
                        <p style={{ textAlign: "center", color: "red", margin: "32px 0" }}>
                            {error}
                        </p>
                    )}

                    {!loading && !error && Object.keys(clipsByDate).length === 0 && (
                        <p style={{ textAlign: "center", color: "#888", margin: "32px 0" }}>
                            Nenhum clipe encontrado.
                        </p>
                    )}

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
