import { useNavigate } from "react-router-dom";
import { ClipCard, ClipData } from "../../components/clip-card/ClipCard";
import { Grid } from "../../components/grid/Grid";
import './ProcessingClips.css'
import placeholderImg from '../../assets/placeholder.png';
import { DownloadCloud, RefreshCw } from "lucide-react";

export default function ProcessingClipsPage() {
    const navigate = useNavigate();

    const mockClips: ClipData[] = [
        { id: '1', title: 'CLIP#001', status: 'completed', thumbnailUrl: placeholderImg, duration: '0:15' },
        { id: '2', title: 'CLIP#002', status: 'completed', thumbnailUrl: placeholderImg, duration: '0:15' },
        { id: '3', title: 'CLIP#003', status: 'completed', thumbnailUrl: placeholderImg, duration: '0:15' },
        { id: '4', title: 'CLIP#004', status: 'completed', thumbnailUrl: placeholderImg, duration: '0:15' },
        { id: '5', title: 'CLIP#005', status: 'completed', thumbnailUrl: placeholderImg, duration: '0:15' },
        { id: '6', title: 'CLIP#006', status: 'completed', thumbnailUrl: placeholderImg, duration: '0:15' },
        { id: '7', title: 'CLIP#007', status: 'completed', thumbnailUrl: placeholderImg, duration: '0:15' },
        { id: '8', title: 'CLIP#008', status: 'completed', thumbnailUrl: placeholderImg, duration: '0:15' },
        { id: '9', title: 'CLIP#009', status: 'completed', thumbnailUrl: placeholderImg, duration: '0:15' },
        { id: '10', title: 'CLIP#010', status: 'completed', thumbnailUrl: placeholderImg, duration: '0:15' },
        { id: '11', title: 'CLIP#011', status: 'completed', thumbnailUrl: placeholderImg, duration: '0:15' },
        { id: '12', title: 'CLIP#012', status: 'completed', thumbnailUrl: placeholderImg, duration: '0:15' },
    ];

    return (
        <div className="page-container bg-gradient">
            <div className="white-container big">
                <div className="processing-header">
                    <h2 className="processing-title">Seus clipes estão prontos!</h2>
                    
                    <div className="progress-bar-container">
                        <div className="progress-bar-fill finished" />
                    </div>
                </div>

                <Grid>
                    {mockClips.map(clip => (
                        <ClipCard key={clip.id} clip={clip} />
                    ))}
                </Grid>

                <div className="clips-actions-container">
                    <button className="btn icon btn-secondary" onClick={() => navigate("/select-player")}>
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
    );
}