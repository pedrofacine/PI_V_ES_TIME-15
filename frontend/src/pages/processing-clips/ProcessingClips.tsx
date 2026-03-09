import { useEffect, useState } from "react";
import { ClipCard, ClipData } from "../../components/clip-card/ClipCard";
import { Grid } from "../../components/grid/Grid";
import './ProcessingClips.css'
import placeholderImg from '../../assets/placeholder.png';
import { DownloadCloud, RefreshCw } from "lucide-react";

export default function ProcessingClipsPage() {
    const mockClips: ClipData[] = [
        { id: '1', title: 'CLIP#001', status: 'completed', thumbnailUrl: placeholderImg, duration: '0:15' },
        { id: '2', title: 'CLIP#002', status: 'generating', progress: 45 },
        { id: '3', title: 'CLIP#003', status: 'error' }
    ];  
    const [isDone, setIsDone] = useState(false);


    return(
        <div className="page-container bg-gradient">
            <div className="white-container big">
                <div className="processing-header">
                    <h2 className="processing-title">{!isDone ? "Recortando os lances do jogador escolhido...": "Os clipes estão prontos!"}</h2>
                    
                    <div className="progress-bar-container">
                        <div className={`progress-bar-fill ${!isDone ? 'animating' : 'finished'}`} />
                    </div>
                </div>

                <Grid>
                    {mockClips.map(clip => (
                        <ClipCard 
                            key={clip.id} 
                            clip={clip} 
                        />
                    ))}
                </Grid>

                <div className="clips-actions-container">
                    <button className="btn icon btn-secondary"
                        onClick={() => {
                            setIsDone(!isDone)
                        }}
                    >
                        <RefreshCw size={18} />
                        Fazer nova análise
                    </button>

                    <button className="btn icon btn-primary">
                        <DownloadCloud size={18} />
                        Baixar todos os clipes
                    </button>
                </div>
            </div>
        </div>
    )
}