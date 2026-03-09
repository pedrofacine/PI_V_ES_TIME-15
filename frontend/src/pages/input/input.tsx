import { ArrowRight, Image, VideoIcon, X } from "lucide-react";
import React, { SyntheticEvent, useRef, useState, useEffect } from "react";
import './input.css';

export default function InputPage() {
    // Refs
    const fileInputRef = useRef<HTMLInputElement>(null);
    const videoInputRef = useRef<HTMLInputElement>(null);
    const [refNumber, setRefNumber] = useState<number | string>("");

    // Estados
    const [imageFile, setImageFile] = useState<File | null>(null); 
    const [imagePreview, setImagePreview] = useState<string>(""); 

    const [videoFile, setVideoFile] = useState<File | null>(null);
    const [videoPreview, setVideoPreview] = useState<string>("");

    const [isDragging, setIsDragging] = useState<boolean>(false);

    useEffect(() => {
        if (!imageFile) {
            setImagePreview("");
            return;
        }
        const objectUrl = URL.createObjectURL(imageFile);
        setImagePreview(objectUrl);
        return () => URL.revokeObjectURL(objectUrl);
    }, [imageFile]);

    useEffect(() => {
        if (!videoFile) {
            setVideoPreview("");
            return;
        }
        const objectUrl = URL.createObjectURL(videoFile);
        setVideoPreview(objectUrl);
        return () => URL.revokeObjectURL(objectUrl);
    }, [videoFile]);

    const handleImageClick = () => fileInputRef.current?.click();
    
    const handleImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) setImageFile(file);
    }

    const removeImage = (e: SyntheticEvent) => {
        e.stopPropagation();
        setImageFile(null);
        if (fileInputRef.current) fileInputRef.current.value = "";
    };

    const handleVideoClick = () => videoInputRef.current?.click();

    const handleVideoChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) setVideoFile(file);
    }

    const removeVideo = (e: SyntheticEvent) => {
        e.stopPropagation();
        setVideoFile(null);
        if (videoInputRef.current) videoInputRef.current.value = "";
    };

    const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        setIsDragging(true); 
    };

    const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        setIsDragging(false); 
    };

    const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        setIsDragging(false);
        const file = e.dataTransfer.files?.[0];
        // Validação simples para garantir que é um vídeo
        if (file && file.type.startsWith('video/')) {
            setVideoFile(file);
        }
    };

    const handleNumberChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const value = e.target.value;

        //permite o campo ficar vazio para deletar
        if (value === "") {
            setRefNumber("");
            return;
        }

        const num = parseInt(value, 10);

        //so atualiza se estiver no intervalo desejado
        if (num >= 1 && num <= 999) {
            setRefNumber(num);
        }
    };

    return (
        <div className="page-container bg-gradient">
            <div className="white-container">
                
                {/* Inputs Ocultos */}
                <input
                    ref={fileInputRef}
                    id="image-upload"
                    type="file" 
                    accept="image/*" 
                    style={{ display: 'none' }} 
                    onChange={handleImageChange}
                />
                <input
                    ref={videoInputRef}
                    id="video-upload"
                    type="file" 
                    accept="video/*" 
                    style={{ display: 'none' }} 
                    onChange={handleVideoChange}
                />

                {/* Área de Upload / Preview de Vídeo */}
                {videoPreview ? (
                    <div className="video-preview-wrapper">
                        <video 
                            src={videoPreview} 
                            controls 
                            className="video-preview-element"
                        />
                        <button onClick={removeVideo} title="Remover vídeo" className="btn-remove-video">
                            <X size={16} strokeWidth={3} />
                        </button>
                    </div>
                ) : (
                    <div 
                        className={`upload-area ${isDragging ? 'dragging' : ''}`} 
                        onClick={handleVideoClick}
                        onDragOver={handleDragOver}
                        onDragLeave={handleDragLeave} // Novo evento adicionado
                        onDrop={handleDrop}
                    >
                        <VideoIcon size={128} color="black" strokeWidth={0.5} />
                        <p className="upload-area-text">
                            <span>Clique para selecionar</span> ou arraste<br/>o seu vídeo aqui
                        </p>
                    </div>
                )}

                {/* Container dos Inputs Auxiliares */}
                <div className="inputs-row">
                    <div className="input-group" style={{ flex: 1, textAlign: 'left' }}>
                        <label className="input-label">Número de referência (0-999)</label>
                        <div className="input-wrapper">
                            <input 
                                type="number" 
                                className="input-base" 
                                placeholder="Ex: 10" 
                                min="1"
                                max="999"
                                value={refNumber}
                                onChange={handleNumberChange}
                                onKeyDown={(e) => {
                                    if (["e", "E", "+", "-", "."].includes(e.key)) {
                                        e.preventDefault();
                                    }
                                }}
                            />
                        </div>
                    </div>

                    <div className="input-group" style={{ flex: 1, textAlign: 'left' }}>
                        <label className="input-label">Imagem de referência (opcional)</label>
                        
                        {imagePreview ? (
                            <div className="image-preview-wrapper preview-container">
                                <img
                                    src={imagePreview}
                                    alt="Preview tático"
                                    className="image-preview-img"
                                />
                                <button 
                                    onClick={removeImage}
                                    title="Remover imagem"
                                    className="btn-remove-preview"
                                >
                                    <X size={12} strokeWidth={3} />
                                </button>
                            </div>    
                        ) : (
                            <div 
                                className="input-wrapper image-select-wrapper" 
                                onClick={handleImageClick} 
                            >
                                <span className="input-icon">
                                    <Image size={18} /> 
                                </span> 

                                <div className="input-base with-icon image-select-text">
                                    Selecionar imagem
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                <button className="btn btn-primary btn-analyze">
                        Iniciar análise 
                        <ArrowRight size={20} className="btn-analyze-icon" />
                </button>
            </div>
        </div>
    );
}