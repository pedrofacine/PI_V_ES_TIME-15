import React, { useEffect, useMemo, useState } from "react";
import { ClipCard, ClipData } from "../../components/clip-card/ClipCard";
import { Grid } from "../../components/grid/Grid";
import './ClipsHistory.css'
import { Search, ChevronDown, Trash2 } from "lucide-react";
import { listClips, deleteJobClips, ClipHistoryGroup } from "../../services/api";

type ClipWithDate = ClipData & { generatedAt: string; videoUrl?: string; jobId: string };

function parseGeneratedAt(generatedAt: string): number {
    const [datePart, timePart] = generatedAt.split(" - ");
    const [day, month, year] = datePart.split("/").map(Number);
    const [hour, minute] = timePart.split(":").map(Number);
    return new Date(year, month - 1, day, hour, minute).getTime();
}

function groupToClips(group: ClipHistoryGroup): ClipWithDate[] {
    return group.clips.map((clip, i) => ({
        id:           clip.id,
        title:        `CLIP#${String(i + 1).padStart(3, "0")}`,
        status:       "completed" as const,
        thumbnailUrl: undefined,
        duration:     clip.duration,
        generatedAt:  group.generated_at,
        videoUrl:     clip.file_url,
        jobId:        group.job_id,
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

    function handleClipDeleted(clipId: string) {
        setGroups(prev =>
            prev
                .map(group => ({ ...group, clips: group.clips.filter(c => c.id !== clipId) }))
                .filter(group => group.clips.length > 0)
        );
        setModalSession(prev => {
            if (!prev) return prev;
            const clips = prev.clips.filter(c => c.id !== clipId);
            return clips.length > 0 ? { ...prev, clips } : null;
        });
    }

    async function handleDeleteJobs(jobIds: string[], clipCount: number) {
        const label = jobIds.length > 1 ? "essa sessão" : "esse job";
        const confirmed = window.confirm(
            `Apagar ${label} do histórico? Isso vai apagar permanentemente os ${clipCount} clipe(s) gerados. Essa ação não pode ser desfeita.`
        );
        if (!confirmed) return;

        try {
            await Promise.all(jobIds.map(id => deleteJobClips(id)));
            const idsToRemove = new Set(jobIds);
            setGroups(prev => prev.filter(g => !idsToRemove.has(g.job_id)));
            setModalSession(prev => {
                if (!prev) return prev;
                const clips = prev.clips.filter(c => !idsToRemove.has(c.jobId));
                return clips.length > 0 ? { ...prev, clips } : null;
            });
        } catch (err) {
            console.error("Erro ao apagar job:", err);
            alert("Não foi possível apagar os clipes desse job. Tente novamente.");
        }
    }

    const filteredClips = useMemo(() => {
        const normalized = search.trim().toLowerCase();
        const filtered = allClips.filter(clip =>
            !normalized || clip.title.toLowerCase().includes(normalized)
        );
        return filtered.sort((a, b) => {
            const diff = parseGeneratedAt(a.generatedAt) - parseGeneratedAt(b.generatedAt);
            return sortBy === "recent" ? -diff : diff;
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
        <div className="history-page">
            <div className="history-card">

                {/* ── Header ── */}
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
                            <select
                                value={sortBy}
                                onChange={(e) => setSortBy(e.target.value as "recent" | "oldest")}
                            >
                                <option value="recent">Mais recente</option>
                                <option value="oldest">Mais antigo</option>
                            </select>
                            <ChevronDown size={16} />
                        </label>
                    </div>
                </header>

                {/* ── Divider ── */}
                <div className="progress-bar-container">
                    <div className="progress-bar-fill finished" />
                </div>

                {/* ── Conteúdo scrollável ── */}
                <div className="scrollable-content">
                    {loading && (
                        <p style={{ textAlign: "center", color: "rgba(255,255,255,0.4)", margin: "32px 0" }}>
                            Carregando clipes...
                        </p>
                    )}

                    {error && (
                        <p style={{ textAlign: "center", color: "#f87171", margin: "32px 0" }}>
                            {error}
                        </p>
                    )}

                    {!loading && !error && Object.keys(clipsByDate).length === 0 && (
                        <p style={{ textAlign: "center", color: "rgba(255,255,255,0.4)", margin: "32px 0" }}>
                            Nenhum clipe encontrado.
                        </p>
                    )}

                    {Object.entries(clipsByDate).map(([date, clips], index) => (
                        <React.Fragment key={date}>
                            <section className="clip-group">
                                <div className="clip-group-header">
                                    <span>Clipes gerados em: </span>
                                    <span className="clip-group-date">{date}</span>
                                    <button
                                        className="clip-group-delete-button"
                                        onClick={() => handleDeleteJobs([...new Set(clips.map(c => c.jobId))], clips.length)}
                                        title="Apagar todos os clipes dessa sessão"
                                        aria-label={`Apagar todos os clipes gerados em ${date}`}
                                    >
                                        <Trash2 size={18} />
                                    </button>
                                </div>

                                <Grid>
                                    {clips.slice(0, 5).map(clip => (
                                        <ClipCard key={clip.id} clip={clip} onDeleted={handleClipDeleted} />
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

                            {index < Object.entries(clipsByDate).length - 1 && (
                                <hr className="group-separator" />
                            )}
                        </React.Fragment>
                    ))}
                </div>

                {/* ── Footer ── */}
                <div className="footer-note">
                    Os clipes ficam armazenados por até 14 dias após sua geração no nosso site
                </div>
            </div>

            {/* ── Modal ── */}
            {modalSession && (
                <div className="modal-overlay" onClick={() => setModalSession(null)}>
                    <div className="modal-content" onClick={e => e.stopPropagation()}>
                        <div className="modal-header">
                            <span>Clipes gerados em: <strong>{modalSession.date}</strong></span>
                            <div className="modal-header-actions">
                                <button
                                    className="modal-delete-button"
                                    onClick={() => handleDeleteJobs([...new Set(modalSession.clips.map(c => c.jobId))], modalSession.clips.length)}
                                    title="Apagar todos os clipes dessa sessão"
                                    aria-label="Apagar todos os clipes dessa sessão"
                                >
                                    <Trash2 size={20} />
                                </button>
                                <button onClick={() => setModalSession(null)}>✕</button>
                            </div>
                        </div>
                        <Grid>
                            {modalSession.clips.map(clip => (
                                <ClipCard key={clip.id} clip={clip} onDeleted={handleClipDeleted} />
                            ))}
                        </Grid>
                    </div>
                </div>
            )}
        </div>
    );
}