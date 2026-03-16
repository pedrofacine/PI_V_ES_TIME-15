import React from 'react';
import './Grid.css';

interface GridProps {
    children: React.ReactNode;
}

export function Grid({ children }: GridProps) {
    return (
        <div className="generic-grid">
            {children}
        </div>
    );
}