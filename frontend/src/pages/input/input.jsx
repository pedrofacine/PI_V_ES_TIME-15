import { ArrowRight, Image, VideoIcon } from "lucide-react";

export default function InputPage() {
    return (
        <div className="page-container bg-gradient">
            <div className="white-container">
                <div style={{
                    width: '100%',
                    maxWidth: '400px',
                    border: '2px dashed #CBDDE9',
                    borderRadius: '16px',
                    padding: '3rem 2rem',
                    textAlign: 'center',
                    cursor: 'pointer',
                    color: '#64748B'
                }}>
                    <VideoIcon size={128} color="black" strokeWidth={0.5} />
                    <p style={{ fontWeight: 500, fontSize: '0.95rem' }}>
                        <span style={{ textDecoration: 'underline' }}>Clique para selecionar</span> ou arraste<br/>o seu vídeo aqui
                    </p>
                </div>

                <div style={{ display: 'flex', flexDirection: 'row', gap: '1rem', width: '100%' }}>

                    <div className="input-group" style={{ flex: 1, textAlign: 'left' }}>
                        <label className="input-label">Número de referência (opcional)</label>
                        <div className="input-wrapper">
                            <input 
                                type="number" 
                                className="input-base" 
                                placeholder="Ex: 10" 
                            />
                        </div>
                    </div>

                    <div className="input-group" style={{ flex: 1, textAlign: 'left' }}>
                        <label className="input-label">Imagem de referência (opcional)</label>
                        <div className="input-wrapper">
                            
                            <span className="input-icon" style={{ display: 'flex', alignItems: 'center', zIndex: 1 }}>
                                <Image size={18} /> 
                            </span> 

                            <input
                                id="image-upload"
                                type="file" 
                                accept="image/*" 
                                style={{ display: 'none' }} 
                            />

                            <label
                                htmlFor="image-upload"
                                className="input-base with-icon"
                                style={{ 
                                    display: 'flex', 
                                    alignItems: 'center', 
                                    cursor: 'pointer', 
                                    color: 'var(--color-input-placeholder)',
                                    margin: 0,
                                    fontWeight: 400
                                }}
                            >
                                Selecionar imagem
                            </label>

                        </div>
                    </div>
                </div>
                <button className="btn btn-primary" style={{ 
                    borderRadius: '24px', 
                    padding: '0.75rem 3rem',
                    gap: '0.5rem',
                    fontSize: '1.05rem'
                }}>
                        Iniciar análise 
                        <ArrowRight size={20} style={{ position: 'relative', top: '1px' }} />
                </button>
            </div>
        </div>
    );
}