import { ArrowRight, Image, VideoIcon, X } from "lucide-react";
import React, { SyntheticEvent, useRef, useState, useEffect, KeyboardEvent } from "react";
import { useNavigate } from "react-router-dom";
import "rc-slider/assets/index.css";
import './input.css';
import { createJob } from "../../services/api";
import Slider from "rc-slider";

// Formata segundos para MM:SS ou HH:MM:SS dependendo da flag hasHours
const formatSecondsToMask = (seconds: number, hasHours: boolean): string => {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);

    if (hasHours) {
        return `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
    }
    return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
};

// Converte a string mascarada de volta para segundos reais
const parseMaskToSeconds = (timeStr: string): number | null => {
    const parts = timeStr.split(":").map(p => parseInt(p, 10));
    if (parts.some(isNaN)) return null;

    if (parts.length === 3) {
        return parts[0] * 3600 + parts[1] * 60 + parts[2];
    } else if (parts.length === 2) {
        return parts[0] * 60 + parts[1];
    } else if (parts.length === 1) {
        return parts[0];
    }
    return null;
};

const applyTimeMask = (value: string, hasHours: boolean): string => {
    let raw = value.replace(/\D/g, "");
    const maxLength = hasHours ? 6 : 4; 
    raw = raw.substring(0, maxLength); 

    if (raw.length > 4) {
        return `${raw.slice(0, 2)}:${raw.slice(2, 4)}:${raw.slice(4)}`;
    } else if (raw.length > 2) {
        return `${raw.slice(0, 2)}:${raw.slice(2)}`;
    }
    return raw;
};

export default function InputPage() {
    const navigate = useNavigate();

    const fileInputRef  = useRef<HTMLInputElement>(null);
    const videoInputRef = useRef<HTMLInputElement>(null);
    const videoElementRef = useRef<HTMLVideoElement>(null);
    
    const [refNumber, setRefNumber] = useState<number | string>("");
    const [imageFile, setImageFile]   = useState<File | null>(null);
    const [imagePreview, setImagePreview] = useState<string>("");
    const [videoFile, setVideoFile]   = useState<File | null>(null);
    const [videoPreview, setVideoPreview] = useState<string>("");
    const [isDragging, setIsDragging] = useState<boolean>(false);

    const [videoDuration, setVideoDuration] = useState<number>(0);
    const [timeRange, setTimeRange] = useState<[number, number]>([0, 0]);

    const [startInputStr, setStartInputStr] = useState<string>("0:00");
    const [endInputStr, setEndInputStr]     = useState<string>("0:00");
    
    const [loading, setLoading] = useState(false);
    const [error, setError]     = useState("");

    const hasHours = videoDuration >= 3600;
    
    useEffect(() => {
        if (!imageFile) { setImagePreview(""); return; }
        const url = URL.createObjectURL(imageFile);
        setImagePreview(url);
        return () => URL.revokeObjectURL(url);
    }, [imageFile]);

    // Reseta estados quando o vídeo muda
    useEffect(() => {
        if (!videoFile) { 
            setVideoPreview(""); 
            setVideoDuration(0);
            setTimeRange([0, 0]);
            setStartInputStr("0:00");
            setEndInputStr("0:00");
            return; 
        }
        const url = URL.createObjectURL(videoFile);
        setVideoPreview(url);
        return () => URL.revokeObjectURL(url);
    }, [videoFile]);

    // Sincroniza os inputs de texto quando o slider é movido
    useEffect(() => {
        if (videoDuration > 0) {
            setStartInputStr(formatSecondsToMask(timeRange[0], hasHours));
            setEndInputStr(formatSecondsToMask(timeRange[1], hasHours));
        }
    }, [timeRange, videoDuration, hasHours]);

    const handleImageClick  = () => fileInputRef.current?.click();
    const handleImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) setImageFile(file);
    };
    const removeImage = (e: SyntheticEvent) => {
        e.stopPropagation();
        setImageFile(null);
        if (fileInputRef.current) fileInputRef.current.value = "";
    };

    const handleVideoClick  = () => videoInputRef.current?.click();
    const handleVideoChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) setVideoFile(file);
    };
    const removeVideo = (e: SyntheticEvent) => {
        e.stopPropagation();
        setVideoFile(null);
        if (videoInputRef.current) videoInputRef.current.value = "";
    };

    const handleDragOver  = (e: React.DragEvent<HTMLDivElement>) => { e.preventDefault(); setIsDragging(true); };
    const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => { e.preventDefault(); setIsDragging(false); };
    const handleDrop      = (e: React.DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        setIsDragging(false);
        const file = e.dataTransfer.files?.[0];
        if (file && file.type.startsWith("video/")) setVideoFile(file);
    };

    const handleNumberChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const value = e.target.value;
        if (value === "") { setRefNumber(""); return; }
        const num = parseInt(value, 10);
        if (num >= 1 && num <= 999) setRefNumber(num);
    };

    const handleLoadedMetadata = () => {
        if (videoElementRef.current) {
            const duration = Math.floor(videoElementRef.current.duration);
            const videoHasHours = duration >= 3600;
            
            setVideoDuration(duration);
            setTimeRange([0, duration]);
            setStartInputStr(formatSecondsToMask(0, videoHasHours));
            setEndInputStr(formatSecondsToMask(duration, videoHasHours));
        }
    };

    // Função de tratamento do input enquanto o usuário digita
    const handleTimeInputChange = (e: React.ChangeEvent<HTMLInputElement>, type: 'start' | 'end') => {
        const maskedValue = applyTimeMask(e.target.value, hasHours);
        if (type === 'start') {
            setStartInputStr(maskedValue);
        } else {
            setEndInputStr(maskedValue);
        }
    };

    const validateAndUpdateTime = (type: 'start' | 'end') => {
        setError("");
        const inputStr = type === 'start' ? startInputStr : endInputStr;
        const currentSeconds = parseMaskToSeconds(inputStr);

        const resetInput = () => {
            if (type === 'start') {
                setStartInputStr(formatSecondsToMask(timeRange[0], hasHours));
            } else {
                setEndInputStr(formatSecondsToMask(timeRange[1], hasHours));
            }
        };

        if (currentSeconds === null) {
            setError("Formato de tempo inválido.");
            resetInput();
            return;
        }

        const clampedSeconds = Math.max(0, Math.min(currentSeconds, videoDuration));
        const [startTime, endTime] = timeRange;

        if (type === 'start') {
            if (clampedSeconds >= endTime) {
                setError("O tempo de início deve ser menor que o de fim.");
                resetInput();
            } else {
                setTimeRange([clampedSeconds, endTime]);
            }
        } else {
            if (clampedSeconds <= startTime) {
                setError("O tempo de fim deve ser maior que o de início.");
                resetInput();
            } else {
                setTimeRange([startTime, clampedSeconds]);
            }
        }
    };

    // Handler para detectar tecla Enter nos inputs
    const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>, type: 'start' | 'end') => {
        if (e.key === 'Enter') {
            validateAndUpdateTime(type);
            e.currentTarget.blur(); // Tira o foco para aplicar o onBlur também (opcional)
        }
    };


    const handleAnalyze = async () => {
        setError("");

        if (!videoFile) {
            setError("Selecione um vídeo antes de continuar.");
            return;
        }
        if (refNumber === "" || Number(refNumber) < 1) {
            setError("Informe o número de referência do jogador.");
            return;
        }

        setLoading(true);
        try {
            const { job_id } = await createJob(
                videoFile, 
                Number(refNumber), 
                timeRange[0], 
                timeRange[1]
            );
            navigate(`/processing-clips/${job_id}`);
        } catch (err: any) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const inputWidthStyle = { width: hasHours ? '90px' : '65px' };

    return (
        <div className="page-container bg-gradient">
            <div className="white-container">

                <input ref={fileInputRef}  id="image-upload" type="file" accept="image/*" style={{ display: "none" }} onChange={handleImageChange} />
                <input ref={videoInputRef} id="video-upload" type="file" accept="video/*" style={{ display: "none" }} onChange={handleVideoChange} />

                {videoPreview ? (
                    <div className="video-preview-wrapper">
                        <div style={{position: "relative"}}>
                            <video 
                                ref={videoElementRef}
                                src={videoPreview} 
                                onLoadedMetadata={handleLoadedMetadata}
                                controls 
                                className="video-preview-element" 
                            />
                            <button onClick={removeVideo} title="Remover vídeo" className="btn-remove-video">
                                <X size={16} strokeWidth={3} />
                            </button>
                        </div>

                        {videoDuration > 0 && (
                            <div className="trim-controls">
                                <p className="trim-title">
                                    Selecione apenas o trecho do vídeo que contém a partida
                                </p>
                                <div className="trim-labels">
                                    <div style={{display: 'flex', alignItems: 'center', gap: '6px'}}>
                                        <span style={{fontSize: '0.8rem', color: '#64748B'}}>Início:</span>
                                        <input 
                                            type="text"
                                            className="time-input-editable"
                                            style={inputWidthStyle}
                                            value={startInputStr}
                                            onChange={(e) => handleTimeInputChange(e, 'start')}
                                            onBlur={() => validateAndUpdateTime('start')}
                                            onKeyDown={(e) => handleKeyDown(e, 'start')}
                                            title={hasHours ? "HH:MM:SS" : "MM:SS"}
                                        />
                                    </div>
                                    
                                    <div style={{display: 'flex', alignItems: 'center', gap: '6px'}}>
                                        <span style={{fontSize: '0.8rem', color: '#64748B'}}>Fim:</span>
                                        <input 
                                            type="text"
                                            className="time-input-editable"
                                            style={inputWidthStyle}
                                            value={endInputStr}
                                            onChange={(e) => handleTimeInputChange(e, 'end')}
                                            onBlur={() => validateAndUpdateTime('end')}
                                            onKeyDown={(e) => handleKeyDown(e, 'end')}
                                            title={hasHours ? "HH:MM:SS" : "MM:SS"}
                                        />
                                    </div>
                                </div>
                                <Slider
                                    range
                                    min={0}
                                    max={videoDuration}
                                    value={timeRange}
                                    onChange={(val) => setTimeRange(val as [number, number])}
                                    allowCross={false}
                                />
                                <p className="trim-hint">
                                    Arraste os tracinhos ou digite o tempo acima para cortar.
                                </p>
                            </div>
                        )}
                        
                    </div>
                ) : (
                    <div
                        className={`upload-area ${isDragging ? "dragging" : ""}`}
                        onClick={handleVideoClick}
                        onDragOver={handleDragOver}
                        onDragLeave={handleDragLeave}
                        onDrop={handleDrop}
                    >
                        <VideoIcon size={128} color="black" strokeWidth={0.5} />
                        <p className="upload-area-text">
                            <span>Clique para selecionar</span> ou arraste<br />o seu vídeo aqui
                        </p>
                    </div>
                )}

                <div className="inputs-row" style={{marginTop: videoPreview ? '1.5rem' : '1rem'}}>
                    {/* ... (Inputs Row mantido igual) */}
                    <div className="input-group" style={{ flex: 1, textAlign: "left" }}>
                        <label className="input-label">Número de referência (0-999)</label>
                        <div className="input-wrapper">
                            <input
                                type="number"
                                className="input-base"
                                placeholder="Ex: 10"
                                min="1" max="999"
                                value={refNumber}
                                onChange={handleNumberChange}
                                onKeyDown={(e) => {
                                    if (["e", "E", "+", "-", "."].includes(e.key)) e.preventDefault();
                                }}
                            />
                        </div>
                    </div>

                    <div className="input-group" style={{ flex: 1, textAlign: "left" }}>
                        <label className="input-label">Imagem de referência (opcional)</label>
                        {imagePreview ? (
                            <div className="image-preview-wrapper preview-container">
                                <img src={imagePreview} alt="Preview tático" className="image-preview-img" />
                                <button onClick={removeImage} title="Remover imagem" className="btn-remove-preview">
                                    <X size={12} strokeWidth={3} />
                                </button>
                            </div>
                        ) : (
                            <div className="input-wrapper image-select-wrapper" onClick={handleImageClick}>
                                <span className="input-icon"><Image size={18} /></span>
                                <div className="input-base with-icon image-select-text">Selecionar imagem</div>
                            </div>
                        )}
                    </div>
                </div>

                {error && (
                    <p style={{ color: "red", fontSize: "0.875rem", marginTop: 8, textAlign: "center" }}>
                        {error}
                    </p>
                )}

                <button
                    className="btn btn-primary btn-analyze"
                    onClick={handleAnalyze}
                    disabled={loading}
                    style={{marginTop: '2rem'}}
                >
                    {loading ? "Enviando..." : "Iniciar análise"}
                    {!loading && <ArrowRight size={20} className="btn-analyze-icon" />}
                </button>

            </div>
        </div>
    );
}